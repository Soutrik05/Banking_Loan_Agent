"""
graph/chat_graph.py
=====================
LangGraph implementation of the conversational loan-assistant flow.

Scope: everything through property verification / selection, plus the new
post-KYC financial-document collection step for brand-new customers. Risk,
credit, loan-eligibility, recommendation and escalation agents don't exist
yet — graph/state.py already defines the schema for them, this graph just
doesn't populate those fields. When those agents are built, extend this
graph with new nodes after "lap" / "home_loan" rather than starting over.

This replaces agents/orchestrator_agent.handle_message(), which routed with
exact-phrase string matching and had no memory between turns. This graph:

  - keeps real conversation memory per session_id (LangGraph MemorySaver
    checkpoint, keyed by thread_id=session_id) — survives across HTTP
    requests since the FastAPI endpoint is otherwise stateless per call
  - uses an LLM router (typo/paraphrase tolerant) instead of brittle
    keyword matching to decide lap vs home_loan vs faq vs a follow-up
    question about properties already shown
  - passes the authenticated customer's profile into the FAQ agent, so it
    stops asking for things we already have on file

Flow shape (new-customer side added on top of the original):

    START → guest (no JWT, not mid-onboarding either)
    START → kyc (no JWT yet, but KYC identity already verified —
                  agents/financial_document_agent.register_pending_applicant
                  was called from main.py's /kyc/verify-identity)
              → financial_document (status checks / questions while the
                  customer uploads docs via the dedicated /kyc/upload
                  endpoint, which auto-completes registration once every
                  required document type is in)
              → END
    START → authed_entry (real JWT — existing customers AND brand-new
              customers whose registration has just completed) → ... →
              END

Note the new-customer's financial_document node never has to hand off to
authed_entry itself: once /kyc/upload's auto-registration succeeds the
frontend gets back a JWT, and the very next /chat call for that session
arrives WITH a token, so _route_entry sends it to "authed" and
_authed_entry_node's existing first-touch branch (stage == "new") fires
the property-question welcome exactly as it does for an existing
customer — no extra chaining code needed.
"""

import json
import operator
import os
import re
from typing import Annotated, Literal, Optional, TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from openai import AzureOpenAI

from agents.account_discovery_agent import discover_account, get_property_question
from agents.property_agent import get_property_choice_message, get_bank_inventory, _load_bank_inventory
from agents.faq_agent import faq_agent
from agents.financial_document_agent import (
    get_financial_document_request,
    get_temp_id_for_session,
    get_upload_status,
    is_awaiting_documents,
)
from session_store import (
    get_session, mark_step, set_credit,
    get_customer_approved_emi, set_customer_approved_emi,
)
from database.appointments import get_appointment, cancel_appointment
from agents.property_verification_agent import verify_property, verify_seller_property
from agents.property_valuation_agent import valuate_property
from agents.risk_assessment_agent import assess_risk
from agents.credit_assessment_agent import assess_credit
from agents.loan_decision_agent import make_loan_decision
from agents.financial_advisor_agent import get_financial_advice
from prompts.router_prompt import ROUTER_SYSTEM_PROMPT, PROPERTY_QA_SYSTEM_PROMPT
from utils.config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_VERSION,
    CHAT_DEPLOYMENT,
)

_client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version=AZURE_OPENAI_API_VERSION,
)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class ChatState(TypedDict, total=False):
    message: str
    session_id: str
    user_context: Optional[dict]
    customer_profile: Optional[dict]
    chat_history: Annotated[list, operator.add]
    stage: Literal[
        "new", "awaiting_property_choice", "awaiting_tie_up_choice", "lap_flow",
        "inventory_flow", "own_choice", "general",
        "tie_ups_property_selected",
        "awaiting_acquisition_type",
        "awaiting_own_choice_address", "awaiting_own_choice_price",
        "property_document_requested", "property_verification", "property_valuation",
        "risk_assessment", "credit_assessment",
        "awaiting_appointment_decision", "awaiting_appointment_form",
        "awaiting_cancel_confirmation",
        "awaiting_address_confirmation",
        "awaiting_advisor_decision", "financial_advisor",
    ]
    shown_properties: list
    selected_property_id: Optional[str]
    # Flow 2A (tie-ups): full properties.json record of the property the
    # customer confirmed with "Continue with this" — the pre-verified
    # valuation/eligibility figures come straight from this dict.
    selected_property_data: Optional[dict]
    just_handled: bool  # set by authed_entry/kyc every turn; True only when the node produced the terminal reply itself

    # Own-choice (Flow 2B) property purchase details, collected via the
    # instant own_choice_* nodes below — zero LLM calls.
    own_choice_address: Optional[str]
    own_choice_price: Optional[float]
    flow_type: Optional[str]  # "lap" | "own_choice" | "tie_ups"

    # LAP property pipeline: Sale Deed fields confirmed by the user, plus the
    # results of the two agent checks that run against them.
    property_data: Optional[dict]
    property_verification_result: Optional[dict]
    valuation_result: Optional[dict]
    risk_assessment_result: Optional[dict]
    credit_assessment_result: Optional[dict]
    loan_decision_result: Optional[dict]

    # "How did you acquire this property?" — determines which documents
    # are required before the property pipeline can proceed.
    acquisition_type: Optional[str]
    required_documents: Optional[list]

    # Manual-review appointment booking, offered when property verification
    # comes back as "manual_review" rather than a clean approve/reject.
    appointment_booked: Optional[bool]
    appointment_data: Optional[dict]

    # Real cancellation flow for an existing appointment — the id of the
    # appointment awaiting a yes/no confirmation to actually cancel.
    pending_cancel_appointment_id: Optional[str]

    # Flow 2B address-mismatch confirmation: the parsed PROPERTY_DATA JSON
    # dict stored while waiting for the user's locality-mismatch answer.
    pending_property_data: Optional[dict]

    # New-customer, pre-JWT onboarding stage (KYC identity verified, financial
    # documents being collected). Kept separate from `stage` above: once
    # registration completes this same thread_id becomes "authed", and
    # `stage` needs to still read as "new" at that point so authed_entry's
    # first-touch welcome fires correctly.
    onboarding_stage: Literal["awaiting_documents"]

    # State preservation
    current_agent: Optional[str]

    # Output fields — every terminal node sets ALL of these explicitly
    # (via _output() below) so a stale value from a previous turn never
    # leaks into a response it doesn't belong to.
    reply: str
    response_type: str
    options: Optional[list]
    properties: Optional[list]
    doc_type: Optional[str]
    sources: Optional[list]
    metadata: Optional[dict]


def _output(message, reply, response_type, *, options=None, properties=None,
            doc_type=None, sources=None, metadata=None, **extra) -> dict:
    return {
        "reply": reply,
        "response_type": response_type,
        "options": options,
        "properties": properties,
        "doc_type": doc_type,
        "sources": sources,
        "metadata": metadata,
        "chat_history": [
            {"role": "user", "content": message},
            {"role": "assistant", "content": reply},
        ],
        **extra,
    }


# Constants for prompts and options
WELCOME_CHOICE_OPTIONS = [
    {"id": "lap", "label": "I own a property"},
    {"id": "home_loan", "label": "I want to buy a property"},
]

TIE_UP_OPTIONS = [
    {"id": "tie_ups", "label": "Our Tie-ups"},
    {"id": "own_choice", "label": "My Own Choice"},
]

EXPLAIN_CHOICE_OPTIONS = [
    {"id": "lap", "label": "I own a property (LAP)"},
    {"id": "home_loan", "label": "I want to buy a new property"},
]

LAP_FLOW_PROMPT = (
    "Perfect. To verify your property I'll need a few details from your "
    "Sale Deed — the registration number, the address, and the area in sq. ft. "
    "You can upload the document and I'll extract these, or type them in directly."
)

HOME_LOAN_PROMPT = (
    "Would you like to choose a property from our verified pre-approved developer tie-ups "
    "in Kolkata, or do you have a different new property in mind?"
)

EXPLAIN_CHOICE_PROMPT = (
    "Certainly! Here is an explanation of the two home loan paths we offer:\n\n"
    "1. **Loan Against Property (LAP)**: This option allows you to mortgage or leverage a property "
    "you ALREADY own (like your home, flat, or land) to secure a loan. You can use these funds for personal or business needs.\n\n"
    "2. **New Property Loan**: This is a standard home loan used to finance the purchase of a new property that you "
    "do not own yet. You can purchase a property from our pre-approved developer tie-ups in Kolkata (which are fast-tracked "
    "and skip extra inspections) or a new property of your own choice.\n\n"
    "Which of these paths would you like to proceed with?"
)

OWN_CHOICE_PROMPT = (
    "Understood. You can choose to finance your own chosen new property. "
    "To get started, please share the property details with me (such as address and price) "
    "or upload any property documents you have on hand for our team to review."
)

OWN_CHOICE_ADDRESS_PROMPT = "What is the full address of the property you want to purchase?"
OWN_CHOICE_PRICE_PROMPT = "What is the approximate purchase price? (e.g. 75 lakhs, 1.5 crore, 2 Cr)"
OWN_CHOICE_PRICE_TOO_LOW = "Please verify — ₹{price} seems unusually low. Please re-enter the purchase price."
OWN_CHOICE_PRICE_TOO_HIGH = "For properties above ₹10 Crore, please visit our branch for specialized assistance."
OWN_CHOICE_PRICE_INVALID = "Sorry, I couldn't understand that price. Please enter it like '75 lakhs', '1.5 crore', or '2 Cr'."
OWN_CHOICE_DOC_PROMPT = "Please upload these documents from the seller:"
OWN_CHOICE_REQUIRED_DOCUMENTS = ["sale_deed", "encumbrance_certificate", "noc_builder"]

# ---------------------------------------------------------------------------
# Account-query and financial-advisor keyword detection — instant, checked
# BEFORE the LLM router. Purely text-based, works for any customer.
# ---------------------------------------------------------------------------

ACCOUNT_QUERY_KEYWORDS = [
    "my account", "bank account", "account number", "account details",
    "loan status", "my loan", "loan details", "approved loan",
    "when will i get", "disbursement", "money in bank",
    "which account", "my emi", "how much emi",
    "outstanding", "outstanding amount", "how much do i owe",
    "my balance", "how much money",
    "my fd", "fixed deposit", "my savings",
    "tell about my bank", "accounts in your bank",
    "my loan status",
]

FINANCIAL_ADVISOR_KEYWORDS = [
    "fd", "break fd", "emi reduce", "prepay", "invest",
    "cibil improve", "tenure", "save money", "afford",
    "financial advice", "recommend", "suggest", "broke",
    "need money", "help me financially",
]

ADVISOR_YES_LABELS = ("yes, help me", "yes help me")
ADVISOR_NO_LABELS = ("no, thanks", "no thanks")

POST_DECISION_ADVICE_PROMPT = "Would you like personalised financial recommendations?"
POST_DECISION_ADVICE_OPTIONS = [
    {"id": "advisor_yes", "label": "Yes, help me"},
    {"id": "advisor_no", "label": "No, thanks"},
]


def _matches_keywords(message: str, keywords: list) -> bool:
    """Word-boundary keyword match so short keywords like 'fd' don't fire
    inside unrelated words. Case-insensitive, works on any message text."""
    lower = (message or "").lower()
    return any(re.search(r"\b" + re.escape(k), lower) for k in keywords)


# Helper to restore UI elements based on state stage
def resume_workflow(state: ChatState) -> dict:
    stage = state.get("stage", "general")
    
    res = {
        "stage": stage,
        "response_type": "text",
        "options": None,
        "properties": None,
        "doc_type": None,
    }
    
    if stage == "awaiting_property_choice":
        card = get_property_choice_message()
        res["reply"] = card["message"]
        res["response_type"] = "mcq"
        res["options"] = card["options"]
    elif stage == "awaiting_tie_up_choice":
        res["reply"] = HOME_LOAN_PROMPT
        res["response_type"] = "mcq"
        res["options"] = TIE_UP_OPTIONS
    elif stage == "inventory_flow":
        shown = state.get("shown_properties", [])
        res["reply"] = (
            f"Here are {len(shown)} premium developer tie-up properties available in Kolkata, "
            "all pre-approved and fast-tracked for financing. Please select one or ask me any questions about them:"
        )
        res["response_type"] = "property_list"
        res["properties"] = shown
        if state.get("selected_property_id"):
            res["options"] = [{"id": "continue", "label": "Continue with this"}]
    elif stage == "lap_flow":
        res["reply"] = LAP_FLOW_PROMPT
        res["response_type"] = "document_request"
        res["doc_type"] = "sale_deed"
    elif stage == "own_choice":
        res["reply"] = OWN_CHOICE_PROMPT
        res["response_type"] = "text"
    elif stage == "awaiting_own_choice_address":
        res["reply"] = OWN_CHOICE_ADDRESS_PROMPT
        res["response_type"] = "text"
    elif stage == "awaiting_own_choice_price":
        res["reply"] = OWN_CHOICE_PRICE_PROMPT
        res["response_type"] = "text"
    else:
        res["reply"] = "How can I help you today?"
        res["response_type"] = "text"
        
    return res

# Helper to construct output and merge state variables into ChatState
def _make_node_output(state: ChatState, reply: str, response_type: str, stage: str, current_agent: str, *,
                      options=None, properties=None, doc_type=None, sources=None, metadata=None,
                      selected_property_id=None, shown_properties=None, **extra) -> dict:
    out = _output(state["message"], reply, response_type, options=options, properties=properties,
                  doc_type=doc_type, sources=sources, metadata=metadata, **extra)
    
    out["stage"] = stage
    out["current_agent"] = current_agent
    if selected_property_id is not None:
        out["selected_property_id"] = selected_property_id
    if shown_properties is not None:
        out["shown_properties"] = shown_properties
        
    return out


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def _classify_guest_intent(message: str) -> str:
    """Classifies user message as 'faq' or 'loan_application' in guest mode without orchestrator."""
    try:
        resp = _client.chat.completions.create(
            model=CHAT_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a banking routing classifier. Classify the user message into either:\n"
                        "- 'faq': General informational questions (e.g., eligibility criteria, interest rates, "
                        "required documents, FAQs, calculation requests, greetings, small talk).\n"
                        "- 'loan_application': Explicit requests to start, apply, proceed, or initiate a new loan application "
                        "process (e.g., 'start application', 'apply now', 'apply for a loan', 'I want to apply').\n"
                        "Respond with ONLY the word 'faq' or 'loan_application' and nothing else."
                    )
                },
                {"role": "user", "content": message},
            ],
            temperature=0,
            max_tokens=10,
        )
        intent = resp.choices[0].message.content.strip().lower()
        if intent not in ("faq", "loan_application"):
            return "faq"
        return intent
    except Exception:
        return "faq"


def format_indian_currency(amount: int) -> str:
    s = str(amount)
    if len(s) <= 3:
        return s
    last_three = s[-3:]
    remaining = s[:-3]
    parts = []
    while len(remaining) > 2:
        parts.append(remaining[-2:])
        remaining = remaining[:-2]
    if remaining:
        parts.append(remaining)
    parts.reverse()
    return ",".join(parts) + "," + last_three


def _guest_node(state: ChatState) -> dict:
    message = state["message"]
    lower = message.lower().strip()

    # Intercept "Just Browsing" welcome flow
    if lower == "just browsing":
        reply = "Hello! I'm Arjun, your dedicated relationship manager. How can I help you today?"
        return _output(message, reply, "text")

    if "where" in lower and "database" in lower and ("property" in lower or "properties" in lower):
        reply = "The property database is located at `backend/mock_data/properties.json`."
        return _output(message, reply, "text")

    wants_property_flow = (
        "own a property" in lower
        or "loan against" in lower
        or "buy a property" in lower
        or "buy a new property" in lower
    )
    intent = "loan_application" if wants_property_flow else _classify_guest_intent(message)

    if intent == "loan_application":
        reply = "I am happy to continue with your application, please login."
        return _output(message, reply, "auth_required")

    answer, scored_docs = faq_agent(message, state.get("chat_history", []))
    return _output(message, answer, "text", sources=scored_docs)


def _loan_already_approved_node(state: ChatState) -> dict:
    """Reached via _route_entry's very first check (see above) — fires
    instantly, before any other routing, whenever this session already has
    an approved loan_decision_result. Deliberately uses _output() rather
    than _make_node_output() so "stage" is left untouched in the returned
    dict: the persisted stage stays exactly what it already was."""
    decision_result = state.get("loan_decision_result") or {}
    card = decision_result.get("display_card") or {}
    reply = (
        "You already have an approved loan application in this session.\n\n"
        f"**Approved Amount:** ₹{card.get('loan_amount') or 0:,.0f}\n"
        f"**Interest Rate:** {card.get('interest_rate')}%\n"
        f"**Monthly EMI:** ₹{card.get('monthly_emi') or 0:,.0f}\n\n"
        "Would you like to:\n"
        "- View your approval details again\n"
        "- Start a completely fresh application (click New Application button)"
    )
    return _output(state["message"], reply, "loan_already_approved")


def _kyc_node(state: ChatState) -> dict:
    """Entry point for a brand-new customer who has just passed KYC identity
    verification but doesn't have a JWT yet (registration only completes
    once financial documents are uploaded). On the first chat turn of this
    phase it sends the document-request message and is terminal for the
    turn — mirroring _authed_entry_node's first-touch pattern. Every later
    turn in this phase falls through to financial_document."""
    if not state.get("onboarding_stage"):
        doc_request = get_financial_document_request()
        out = _output(
            state["message"], doc_request["message"], "document_request",
            doc_type="financial_documents",
        )
        out["onboarding_stage"] = "awaiting_documents"
        out["just_handled"] = True
        return out

    return {"just_handled": False}


def _financial_document_node(state: ChatState) -> dict:
    """Handles chat turns while a brand-new customer is uploading their
    financial documents (the uploads themselves go through main.py's
    /kyc/upload, not through chat). Answers status questions directly;
    anything that looks like a real question falls back to faq_agent,
    with a reminder of what's still missing appended."""
    message = state["message"]
    temp_id = get_temp_id_for_session(state.get("session_id", ""))
    status = get_upload_status(temp_id) if temp_id else {"uploaded": {}, "missing": [], "ready": False}

    if "?" in message:
        answer, scored_docs = faq_agent(message, state.get("chat_history", []))
        if status["missing"]:
            answer += "\n\n(Just a reminder — I'm still waiting on: " + ", ".join(status["missing"]) + ".)"
        return _output(message, answer, "text", sources=scored_docs)

    if status["missing"]:
        reply = (
            "Here's what I'm still waiting on:\n"
            + "\n".join(f"- {m}" for m in status["missing"])
            + "\nYou can upload them using the panel above."
        )
    else:
        reply = "Looks like I've got everything I need — just finishing up your account setup."

    return _output(message, reply, "document_request", doc_type="financial_documents")


# Exact button-label matches that mean the property-choice question has
# already been answered — kept in sync with _route_after_entry's matching
# below. Used to stop _authed_entry_node from re-asking the question on a
# fresh thread (e.g. a rotated session_id from "New Application") when the
# user's first message in it is already an answer.
_PROPERTY_CHOICE_ANSWERS = (
    "i own a property", "i own a property (lap)", "lap",
    "i want to buy a property", "i want to buy a new property",
)

# Only stages where it is appropriate to (re-)emit the property-choice MCQ.
# Any other stage means the user has already progressed past that question,
# so the greeting must NEVER fire — even if MemorySaver loses its checkpoint.
PROPERTY_CHOICE_STAGES = {"new", "awaiting_property_choice"}


def _authed_entry_node(state: ChatState) -> dict:
    """Loads/refreshes the customer profile. On the very first authenticated
    turn of a session, also greets and asks the property question directly
    (terminal for this turn) — every later turn falls through to routing.

    The welcome greeting must NEVER re-fire once the customer is already
    past it (lap_flow, property_document_requested, risk_assessment, ...).
    Stage itself already guards this in the normal case (it's only "new"
    on the very first turn of a thread). But MemorySaver is in-memory, so a
    backend restart mid-conversation wipes the checkpoint and makes a
    later turn look like stage=="new" again. The mid_flow_message check
    below is a second, message-shape-based guard so a turn that's clearly
    deep in the property pipeline (e.g. the Sale Deed confirm-and-proceed
    payload) never gets re-greeted even if the persisted stage was lost."""
    user_context = state["user_context"]
    profile = state.get("customer_profile")
    if not profile:
        profile = discover_account(user_context["user_id"], user_context["customer_id"])

    session = get_session(state.get("session_id", ""))
    is_existing = session.get("is_existing")

    stage = state.get("stage", "new")
    selected_property_id = state.get("selected_property_id")
    shown_properties = state.get("shown_properties", [])
    message = state["message"]
    already_answered = message.lower().strip() in _PROPERTY_CHOICE_ANSWERS
    mid_flow_message = "registration_number" in message or message.strip().startswith("PROPERTY_DATA:")

    # Hard guard: only emit the property-choice greeting when the session is
    # genuinely at the beginning.  If stage is anything outside
    # PROPERTY_CHOICE_STAGES the user has already progressed past that step —
    # skip all greeting logic and route their message normally.
    if stage not in PROPERTY_CHOICE_STAGES:
        return {
            "customer_profile": profile,
            "stage": stage,
            "selected_property_id": selected_property_id,
            "shown_properties": shown_properties,
            "current_agent": state.get("current_agent"),
            "just_handled": False,
        }

    if stage == "new":
        # Account/loan-status questions asked as the very first message
        # must be ANSWERED, not swallowed by the welcome MCQ — fall through
        # to routing (which sends them to account_query) without touching
        # stage, so the property-choice question still fires later.
        if _matches_keywords(message, ACCOUNT_QUERY_KEYWORDS):
            return {
                "customer_profile": profile,
                "current_agent": "authed_entry_agent",
                "just_handled": False,
            }
        if mid_flow_message:
            # Don't touch stage at all — _route_after_entry's
            # registration_number short-circuit routes this correctly to
            # property_verification regardless of whatever stage says.
            return {
                "customer_profile": profile,
                "current_agent": "authed_entry_agent",
                "just_handled": False,
            }
        if already_answered:
            # Fresh thread whose first message is already an answer to the
            # property-choice question (e.g. "New Application" re-showed the
            # question locally and the user clicked a button) — skip the
            # duplicate welcome, transition stage, and let the router handle
            # their actual message.
            return {
                "customer_profile": profile,
                "stage": "awaiting_property_choice",
                "current_agent": "authed_entry_agent",
                "just_handled": False,
            }
        # Always emit the property-choice MCQ as a terminal response on the
        # very first authenticated turn.  Using just_handled=True for BOTH
        # new and existing customers ensures the user's message is never
        # silently swallowed into an FAQ answer that then appends the MCQ
        # again, which was the source of the "greeting repeating" bug.
        card = get_property_choice_message()
        first_name = (user_context.get("full_name") or "there").split()[0]
        if is_existing:
            reply = f"Welcome back, {first_name}! {card['message']}"
        else:
            reply = f"Welcome back, {first_name}! {card['message']}"
        return _make_node_output(
            state, reply, "mcq", "awaiting_property_choice", "authed_entry_agent",
            options=card["options"],
            customer_profile=profile,
            just_handled=True
        )

    return {
        "customer_profile": profile,
        "stage": stage,
        "selected_property_id": selected_property_id,
        "shown_properties": shown_properties,
        "current_agent": state.get("current_agent"),
        "just_handled": False
    }


def _lap_node(state: ChatState) -> dict:
    return _make_node_output(
        state, LAP_FLOW_PROMPT, "document_request", "lap_flow", "lap_agent",
        doc_type="sale_deed",
        customer_profile=state.get("customer_profile")
    )


ACQUISITION_TYPE_PROMPT = "How did you acquire this property?"

ACQUISITION_TYPE_OPTIONS = [
    {"label": "I purchased it", "value": "purchased"},
    {"label": "I inherited it", "value": "inherited"},
    {"label": "It was gifted to me", "value": "gifted"},
]

# acquisition_type -> required document types
REQUIRED_DOCS_BY_ACQUISITION = {
    "purchased": ["sale_deed"],
    "inherited": ["succession_certificate", "mutation_certificate"],
    "gifted": ["gift_deed", "mutation_certificate"],
}

ACQUISITION_DOC_REPLIES = {
    "purchased": "Please upload your Sale Deed document.",
    "inherited": "Please upload your Succession Certificate and Mutation Certificate.",
    "gifted": "Please upload your Gift Deed and Mutation Certificate.",
}


def _detect_acquisition_type(message: str) -> Optional[str]:
    """Keyword match against the three acquisition-choice button labels.
    Works regardless of which customer is answering — purely text-based."""
    lower = message.lower().strip()
    if "purchas" in lower or "bought" in lower:
        return "purchased"
    if "inherit" in lower:
        return "inherited"
    if "gift" in lower:
        return "gifted"
    return None


def _acquisition_type_node(state: ChatState) -> dict:
    """Asks how the customer acquired their property, right after they
    choose LAP — instant, no LLM call. Required documents differ by
    acquisition type, so this has to happen before any document upload."""
    return _make_node_output(
        state, ACQUISITION_TYPE_PROMPT, "acquisition_choice",
        "awaiting_acquisition_type", "acquisition_type_agent",
        options=ACQUISITION_TYPE_OPTIONS,
        customer_profile=state.get("customer_profile"),
    )


def _set_document_requirements_node(state: ChatState) -> dict:
    """Detects which acquisition type the customer picked and sets the
    document checklist accordingly — instant, no LLM call. Works the same
    for any customer; nothing here is hardcoded to a specific person."""
    acquisition_type = _detect_acquisition_type(state["message"]) or "purchased"
    required_documents = REQUIRED_DOCS_BY_ACQUISITION[acquisition_type]
    reply = ACQUISITION_DOC_REPLIES[acquisition_type]

    return _make_node_output(
        state, reply, "property_document_upload", "property_document_requested",
        "document_requirements_agent",
        doc_type=required_documents[0],
        metadata={"required_documents": required_documents, "acquisition_type": acquisition_type},
        customer_profile=state.get("customer_profile"),
        acquisition_type=acquisition_type,
        required_documents=required_documents,
    )


def _home_loan_node(state: ChatState) -> dict:
    return _make_node_output(
        state, HOME_LOAN_PROMPT, "mcq", "awaiting_tie_up_choice", "home_loan_agent",
        options=TIE_UP_OPTIONS,
        customer_profile=state.get("customer_profile")
    )


def _explain_choice_node(state: ChatState) -> dict:
    return _make_node_output(
        state, EXPLAIN_CHOICE_PROMPT, "mcq", "awaiting_property_choice", "explain_choice_agent",
        options=EXPLAIN_CHOICE_OPTIONS,
        customer_profile=state.get("customer_profile")
    )


def _show_inventory_node(state: ChatState) -> dict:
    inv = get_bank_inventory()
    reply = (
        f"Here are {inv['count']} premium developer tie-up properties available in Kolkata, "
        "all pre-approved and fast-tracked for financing. Please select one or ask me any questions about them:"
    )
    return _make_node_output(
        state, reply, "property_list", "inventory_flow", "show_inventory_agent",
        properties=inv["properties"],
        shown_properties=inv["properties"],
        flow_type="tie_ups",
        customer_profile=state.get("customer_profile")
    )


# ---------------------------------------------------------------------------
# Flow 2A — Our Tie-ups: property selection → eligibility → risk → credit →
# decision. The bank pre-verified these properties, so there is no document
# upload or registry verification step; eligibility comes straight from the
# inventory record and auto-chains into the same risk/credit/decision
# pipeline as Flow 1.
# ---------------------------------------------------------------------------

TIE_UPS_SELECTED_OPTIONS = [
    {"label": "Check my eligibility", "value": "check eligibility"},
    {"label": "Ask about property", "value": "ask property"},
]

TIE_UPS_QA_OPTIONS = [
    {"label": "Yes, check eligibility", "value": "check eligibility"},
]

TIE_UPS_ELIGIBILITY_NUDGE = (
    "\n\nWould you like to proceed with loan eligibility check for this property?"
)

TIE_UPS_ELIGIBILITY_YES = (
    "check eligibility", "check my eligibility", "yes, check eligibility",
    "yes check eligibility", "yes proceed", "yes, proceed", "yes",
    "yes please", "proceed", "ok", "okay", "sure",
)


def _load_property(property_id: str) -> dict:
    """Loads a single bank-inventory property record from properties.json.
    Returns {} if the id is unknown or the file can't be read."""
    path = os.path.join(os.path.dirname(__file__), "..", "mock_data", "properties.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("bank_inventory", {}).get(property_id, {})
    except Exception:
        return {}


def _tie_ups_selected_node(state: ChatState) -> dict:
    """User confirmed a tie-up property ("Continue with this" or a message
    naming a BINV id) — instant, no LLM call. Stores the full property
    record in state and offers Q&A / eligibility as the next step."""
    message = state["message"]
    session_id = state.get("session_id", "")

    property_id = state.get("selected_property_id")
    match = re.search(r"\b(binv\d{3})\b", message.lower())
    if match:
        property_id = match.group(1).upper()

    prop = _load_property(property_id or "")
    if not prop:
        # No selection on record (e.g. checkpoint lost) — re-show the
        # inventory so the customer can pick again.
        return _show_inventory_node(state)

    mark_step(session_id, "property", "completed")

    reply = (
        f"Great choice! Here's a summary of your selected property:\n\n"
        f"**{prop.get('address', '')}**\n"
        f"Area: {prop.get('area_sqft')} sqft | "
        f"Price: Rs.{(prop.get('listed_price') or 0)/100000:.1f}L\n"
        f"Down Payment: Rs.{(prop.get('down_payment_min') or 0)/100000:.1f}L | "
        f"Max Loan: Rs.{(prop.get('max_loan_available') or 0)/100000:.1f}L\n\n"
        f"Do you have any questions about this property, "
        f"or shall we check your loan eligibility?"
    )

    return _make_node_output(
        state, reply, "mcq", "tie_ups_property_selected", "tie_ups_agent",
        options=TIE_UPS_SELECTED_OPTIONS,
        selected_property_id=property_id,
        shown_properties=state.get("shown_properties", []),
        customer_profile=state.get("customer_profile"),
        selected_property_data=prop,
        flow_type="tie_ups",
    )


def _tie_ups_property_qa_node(state: ChatState) -> dict:
    """Answers questions about the selected tie-up property using its full
    properties.json record (amenities, transit, crime rate, possession
    status, ...), then always nudges towards the eligibility check. Stage
    stays "tie_ups_property_selected" so follow-up questions keep landing
    here until the customer proceeds."""
    message = state["message"]
    prop = state.get("selected_property_data") or _load_property(
        state.get("selected_property_id") or ""
    )

    if message.strip().lower() == "ask property":
        # "Ask about property" button click — no question asked yet.
        answer = "Sure — what would you like to know about this property?"
    else:
        try:
            resp = _client.chat.completions.create(
                model=CHAT_DEPLOYMENT,
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are Arjun, a senior relationship manager at a reputed Indian bank.

The customer has selected the following property from our bank inventory:
{json.dumps(prop, indent=2)}

They are now asking a question about it (e.g., amenities, location, connectivity, crime rate, nearby schools, possession status, pricing, etc.).

Guidelines:
- Use ONLY the provided property JSON data for property-specific details (e.g. amenities, crime_rate, transit, nearby_schools, hospitals, possession_status, listed_price).
- Translate the raw fields into clear, friendly qualitative explanations.
- Be highly concise, direct, and professional.
- Limit responses to 2-3 sentences.
- Don't use markdown tables — plain conversational text only.""",
                    },
                    *state.get("chat_history", [])[-6:],
                    {"role": "user", "content": message},
                ],
                temperature=0.3,
            )
            answer = resp.choices[0].message.content
        except Exception as e:
            answer = f"Sorry, I had trouble pulling that up: {e}"

    return _make_node_output(
        state, answer + TIE_UPS_ELIGIBILITY_NUDGE, "mcq",
        "tie_ups_property_selected", "tie_ups_agent",
        options=TIE_UPS_QA_OPTIONS,
        selected_property_id=state.get("selected_property_id"),
        shown_properties=state.get("shown_properties", []),
        customer_profile=state.get("customer_profile"),
        selected_property_data=prop,
        flow_type="tie_ups",
    )


def _tie_ups_eligibility_node(state: ChatState) -> dict:
    """Flow 2A eligibility — instant, no LLM call. The bank pre-verified
    the tie-up property, so there's no document upload or registry check:
    the valuation comes straight from the inventory record, and this node
    unconditionally chains into risk assessment in the SAME turn (plain
    edge below), exactly like the Flow 1 valuation nodes."""
    session_id = state.get("session_id", "")
    prop = state.get("selected_property_data") or _load_property(
        state.get("selected_property_id") or ""
    )

    listed_price = prop.get("listed_price") or 0
    max_loan = prop.get("max_loan_available") or 0
    ltv_ratio = prop.get("ltv_ratio") or 0.80

    valuation_result = {
        "fair_market_value": listed_price,
        "max_loan": max_loan,
        "ltv_ratio": ltv_ratio,
        "summary": (
            f"✅ Bank pre-verified property. "
            f"Max loan available: Rs.{max_loan/100000:.1f}L "
            f"at {ltv_ratio*100:.0f}% LTV."
        ),
    }

    # Synthetic verification result: the bank already holds this property
    # in inventory, so it counts as verified. government_value carries the
    # listed price so the loan decision card shows the property's actual
    # price rather than a blank "Property Value".
    verification_result = {
        "verified": True,
        "status": "approved",
        "address": prop.get("address"),
        "area_sqft": prop.get("area_sqft"),
        "property_type": prop.get("property_type"),
        "government_value": listed_price,
        "summary": "Bank pre-verified tie-up property — no separate verification needed.",
    }

    mark_step(session_id, "property", "completed")
    mark_step(session_id, "risk", "active", set_active=True)

    return _make_node_output(
        state, valuation_result["summary"], "valuation_result",
        "property_valuation", "tie_ups_eligibility_agent",
        metadata={"valuation_result": valuation_result},
        customer_profile=state.get("customer_profile"),
        selected_property_id=state.get("selected_property_id"),
        selected_property_data=prop,
        valuation_result=valuation_result,
        property_verification_result=verification_result,
        flow_type="tie_ups",
    )


def _own_choice_node(state: ChatState) -> dict:
    """Triggered once, by the literal 'My Own Choice' button click
    (INSTANT_ROUTES). Combines the acknowledgement and the first
    structured question into a single reply so chat_history never gets
    two entries for one user message, and jumps straight to
    "awaiting_own_choice_address" — "own_choice" is never persisted as a
    resumable stage in the normal path (see _own_choice_address_node for
    the resume-only fallback)."""
    combined = f"{OWN_CHOICE_PROMPT}\n\n{OWN_CHOICE_ADDRESS_PROMPT}"
    return _make_node_output(
        state, combined, "text", "awaiting_own_choice_address", "own_choice_agent",
        flow_type="own_choice",
        customer_profile=state.get("customer_profile"),
    )


def _own_choice_address_node(state: ChatState) -> dict:
    """Resume-only fallback for a persisted stage == "own_choice" (e.g.
    after a backend restart, since MemorySaver is in-memory). Normal flow
    never reaches this node — _own_choice_node above already combines this
    question into its own reply and skips straight to
    "awaiting_own_choice_address"."""
    return _make_node_output(
        state, OWN_CHOICE_ADDRESS_PROMPT, "text", "awaiting_own_choice_address", "own_choice_agent",
        flow_type="own_choice",
        customer_profile=state.get("customer_profile"),
    )


def _own_choice_price_node(state: ChatState) -> dict:
    """Stores whatever the user typed as the address, asks for price —
    instant, no LLM call."""
    address = state["message"].strip()
    return _make_node_output(
        state, OWN_CHOICE_PRICE_PROMPT, "text", "awaiting_own_choice_price", "own_choice_agent",
        own_choice_address=address,
        customer_profile=state.get("customer_profile"),
    )


def _parse_indian_price(text: str) -> Optional[float]:
    """Parses '75 lakhs'/'75L', '1.5 crore'/'1.5 Cr', or a plain number
    into an INR float. Returns None if no number is found."""
    cleaned = text.strip().lower().replace(",", "").replace("₹", "")
    match = re.search(r'(\d+(?:\.\d+)?)\s*(crore|cr|lakhs|lakh|l)?\b', cleaned)
    if not match:
        return None
    number = float(match.group(1))
    unit = match.group(2)
    if unit in ("crore", "cr"):
        return number * 1_00_00_000
    if unit in ("lakhs", "lakh", "l"):
        return number * 1_00_000
    return number


def _own_choice_price_parser_node(state: ChatState) -> dict:
    """Parses the purchase price, validates bounds, and — once valid —
    requests the seller-side documents. Instant, no LLM call."""
    price = _parse_indian_price(state["message"])

    if price is None:
        return _make_node_output(
            state, OWN_CHOICE_PRICE_INVALID, "text", "awaiting_own_choice_price", "own_choice_agent",
            customer_profile=state.get("customer_profile"),
        )

    if price < 500000:
        reply = OWN_CHOICE_PRICE_TOO_LOW.format(price=format_indian_currency(int(price)))
        return _make_node_output(
            state, reply, "text", "awaiting_own_choice_price", "own_choice_agent",
            customer_profile=state.get("customer_profile"),
        )

    if price > 100000000:
        return _make_node_output(
            state, OWN_CHOICE_PRICE_TOO_HIGH, "text", "general", "own_choice_agent",
            customer_profile=state.get("customer_profile"),
        )

    return _make_node_output(
        state, OWN_CHOICE_DOC_PROMPT, "property_document_upload", "property_document_requested",
        "own_choice_agent",
        metadata={
            "required_documents": OWN_CHOICE_REQUIRED_DOCUMENTS,
            "acquisition_type": "purchase_new",
            "flow_type": "own_choice",
        },
        customer_profile=state.get("customer_profile"),
        own_choice_price=price,
        required_documents=OWN_CHOICE_REQUIRED_DOCUMENTS,
        acquisition_type="purchase_new",
    )


PROPERTY_DOCUMENT_UPLOAD_PROMPT = (
    "Please upload your Sale Deed document — our AI will automatically extract "
    "the registration number, owner details, and property address from it."
)


def _property_document_upload_node(state: ChatState) -> dict:
    """Asks for the Sale Deed once the customer has chosen LAP / their own
    property, before any property_data has been confirmed. Works for any
    customer's any document — nothing here is hardcoded."""
    return _make_node_output(
        state, PROPERTY_DOCUMENT_UPLOAD_PROMPT, "property_document_upload",
        "property_document_requested", "property_document_upload_agent",
        doc_type="sale_deed",
        customer_profile=state.get("customer_profile"),
    )


_DISCREPANCY_FIELD_LABELS = {
    "registration_number": "registration numbers",
    "owner_name": "owner names",
    "address": "addresses",
}


def _check_document_discrepancies(documents: Optional[dict]) -> Optional[str]:
    """Cross-checks extracted fields across multiple uploaded documents
    (e.g. Succession Certificate vs Mutation Certificate, or Gift Deed vs
    Mutation Certificate) and returns a user-facing discrepancy message if
    any key field disagrees, or None if everything lines up (or there's
    only one document, e.g. a plain Sale Deed)."""
    if not documents or len(documents) < 2:
        return None

    for field, label in _DISCREPANCY_FIELD_LABELS.items():
        distinct_values = {}
        for fields in documents.values():
            value = (fields or {}).get(field)
            if value:
                distinct_values.setdefault(str(value).strip().lower(), value)
        if len(distinct_values) > 1:
            shown = " vs ".join(str(v) for v in distinct_values.values())
            return (
                f"We noticed different {label} in your documents ({shown}). "
                "Please verify and re-upload if needed, or contact support."
            )
    return None


def _parse_property_data_message(message: str) -> tuple:
    """Parses the PROPERTY_DATA JSON payload out of a confirm-and-proceed
    message. Returns (data, None) on success or (None, error_reply) on
    failure — shared by the LAP/multi-doc and own-choice verification
    nodes below."""
    match = re.search(r"\{.*\}", message, re.DOTALL)
    try:
        return json.loads(match.group(0) if match else message), None
    except Exception:
        return None, "Sorry, I couldn't read those property details. Please try uploading the document again."


def _property_verification_node(state: ChatState) -> dict:
    """Triggered when the frontend sends back the confirmed property fields
    (message contains a PROPERTY_DATA JSON payload, regardless of which
    acquisition-type documents produced them). Verifies the property
    against the (mock) land registry for whichever registration
    number/owner/address came through — works for any customer's property.

    If verified, this is chained straight into _risk_assessment_node in the
    SAME turn (see _route_after_verification below) so the user gets one
    combined message without having to say anything else."""
    message = state["message"]
    session_id = state.get("session_id", "")

    data, error_reply = _parse_property_data_message(message)
    if error_reply:
        return _make_node_output(
            state, error_reply, "text", "general", "property_verification_agent",
            customer_profile=state.get("customer_profile"),
        )

    # Multi-document acquisition types (inherited/gifted/own_choice) send
    # per-document OCR fields alongside the merged ones — cross-check them
    # before trusting the merge and proceeding to verification.
    discrepancy = _check_document_discrepancies(data.get("_documents"))
    if discrepancy:
        required_documents = state.get("required_documents") or ["sale_deed"]
        return _make_node_output(
            state, discrepancy, "property_document_upload", "property_document_requested",
            "property_verification_agent",
            doc_type=required_documents[0],
            metadata={
                "required_documents": required_documents,
                "acquisition_type": state.get("acquisition_type"),
                "flow_type": state.get("flow_type"),
            },
            customer_profile=state.get("customer_profile"),
        )

    result = verify_property(
        registration_number=data.get("registration_number"),
        owner_name=data.get("owner_name"),
        owner_pan=data.get("owner_pan"),
        address=data.get("address"),
        area_sqft=data.get("area_sqft"),
    )

    mark_step(session_id, "property", "completed" if result["verified"] else "failed")

    if result.get("status") == "manual_review":
        reply = (
            result["summary"]
            + "\n\nWould you like to book an appointment with our property "
              "verification team to resolve this?"
        )
        return _make_node_output(
            state, reply, "manual_review_appointment", "awaiting_appointment_decision",
            "property_verification_agent",
            customer_profile=state.get("customer_profile"),
            property_data=data,
            property_verification_result=result,
        )

    next_stage = "property_valuation" if result["verified"] else "general"

    return _make_node_output(
        state, result["summary"], "text", next_stage, "property_verification_agent",
        customer_profile=state.get("customer_profile"),
        property_data=data,
        property_verification_result=result,
    )


def _property_valuation_node(state: ChatState) -> dict:
    """Reached only by being chained directly after an approved property
    verification, in the SAME turn (see _route_after_verification) — pure
    calculation, ZERO LLM calls. Simulates a bank-appointed technical
    valuation for whichever property just got verified; nothing here is
    hardcoded to a specific customer or property. Always unconditionally
    chains straight into risk assessment next (see the plain edge in the
    graph wiring below — there's no failure branch for valuation itself)."""
    property_result = state.get("property_verification_result") or {}

    result = valuate_property(
        area_sqft=property_result.get("area_sqft") or 0,
        address=property_result.get("address") or "",
        property_type=property_result.get("property_type") or "residential_apartment",
        registration_number=property_result.get("registration_number") or "",
        government_value=property_result.get("government_value") or 0,
    )

    prior_reply = state.get("reply") or ""
    combined_reply = f"{prior_reply}\n\n{result['summary']}" if prior_reply else result["summary"]

    return _make_node_output(
        state, combined_reply, "valuation_result", "property_valuation", "property_valuation_agent",
        metadata={"valuation_result": result},
        customer_profile=state.get("customer_profile"),
        valuation_result=result,
    )


# ---------------------------------------------------------------------------
# Flow 2B — address locality mismatch detection
# ---------------------------------------------------------------------------

# All Kolkata localities recognised by the mock land-registry API.  Only
# flags a mismatch when BOTH the user-stated address AND the document address
# contain a known locality AND those two localities differ.  "Kolkata" alone
# (no specific area) is intentionally absent — too vague to compare.
_KOLKATA_LOCALITIES = [
    "ballygunge", "salt lake", "new town", "tollygunge",
    "dum dum", "lake town", "entally", "rajarhat",
    "behala", "jadavpur", "kasba", "garia", "howrah",
    "shyambazar", "ultadanga", "liluah", "santragachi",
    "park street", "camac street", "bhowanipore",
    "lake gardens", "alipore", "baranagar", "barasat",
    "thakurpukur", "maheshtala", "shibpur", "narendrapur",
    "santoshpur",
]


def _extract_locality(address: str) -> Optional[str]:
    """Return the first recognised Kolkata locality found in *address*,
    or None if no known locality is present."""
    addr_lower = (address or "").lower()
    for loc in _KOLKATA_LOCALITIES:
        if loc in addr_lower:
            return loc
    return None


def _check_address_mismatch(user_stated: str, doc_address: str) -> bool:
    """Return True only when both addresses contain a known locality AND
    those localities differ — avoids false positives on vague addresses."""
    if not user_stated or not doc_address:
        return False
    stated_loc = _extract_locality(user_stated)
    doc_loc = _extract_locality(doc_address)
    return bool(stated_loc and doc_loc and stated_loc != doc_loc)


def _own_choice_verification_node(state: ChatState) -> dict:
    """Flow 2B (Own Choice): verifies the SELLER's ownership of the
    property the customer wants to buy — not the customer's own ownership,
    since they're the buyer and won't appear on the registry. Reached only
    when flow_type == "own_choice" and the document confirm-and-proceed
    payload comes back (see _route_after_entry's PROPERTY_DATA check).

    If verified, this is chained straight into _own_choice_valuation_node
    in the SAME turn (see _route_after_own_choice_verification), mirroring
    how _property_verification_node chains into _property_valuation_node
    for the LAP flow."""
    message = state["message"]
    session_id = state.get("session_id", "")

    data, error_reply = _parse_property_data_message(message)
    if error_reply:
        return _make_node_output(
            state, error_reply, "text", "general", "own_choice_verification_agent",
            customer_profile=state.get("customer_profile"),
        )

    discrepancy = _check_document_discrepancies(data.get("_documents"))
    if discrepancy:
        required_documents = state.get("required_documents") or OWN_CHOICE_REQUIRED_DOCUMENTS
        return _make_node_output(
            state, discrepancy, "property_document_upload", "property_document_requested",
            "own_choice_verification_agent",
            doc_type=required_documents[0],
            metadata={
                "required_documents": required_documents,
                "acquisition_type": "purchase_new",
                "flow_type": "own_choice",
            },
            customer_profile=state.get("customer_profile"),
        )

    # Address locality mismatch check — compare what the customer said in
    # the "What is the address?" step against what the uploaded documents
    # actually say.  Only flags when BOTH sides have a known Kolkata
    # locality AND those localities differ; vague addresses (e.g. just
    # "Kolkata") are never flagged to avoid false positives.
    user_address = state.get("own_choice_address") or ""
    doc_address = data.get("address") or ""
    if _check_address_mismatch(user_address, doc_address):
        stated_loc = (_extract_locality(user_address) or "").title()
        doc_loc = (_extract_locality(doc_address) or "").title()
        reply = (
            f"We noticed an address mismatch:\n\n"
            f"**You mentioned:** {user_address}\n"
            f"**Document shows:** {doc_address}\n\n"
            f"The property areas don't match ({stated_loc} vs {doc_loc}). "
            f"Please confirm which is correct:"
        )
        return _make_node_output(
            state, reply, "mcq", "awaiting_address_confirmation",
            "own_choice_verification_agent",
            options=[
                {"label": f"Document is correct ({doc_loc})", "id": "confirm_doc"},
                {"label": "Let me re-enter the address", "id": "reenter"},
            ],
            customer_profile=state.get("customer_profile"),
            pending_property_data=data,
        )

    result = verify_seller_property(
        registration_number=data.get("registration_number"),
        seller_name=data.get("owner_name"),
        address=data.get("address"),
        area_sqft=data.get("area_sqft"),
    )

    mark_step(session_id, "property", "completed" if result["verified"] else "failed")

    if result.get("status") == "manual_review":
        reply = (
            result["summary"]
            + "\n\nWould you like to book an appointment with our property "
              "verification team to resolve this?"
        )
        return _make_node_output(
            state, reply, "manual_review_appointment", "awaiting_appointment_decision",
            "own_choice_verification_agent",
            customer_profile=state.get("customer_profile"),
            property_data=data,
            property_verification_result=result,
        )

    next_stage = "property_valuation" if result["verified"] else "general"

    return _make_node_output(
        state, result["summary"], "text", next_stage, "own_choice_verification_agent",
        customer_profile=state.get("customer_profile"),
        property_data=data,
        property_verification_result=result,
    )


def _own_choice_valuation_node(state: ChatState) -> dict:
    """Reached only by chaining directly after an approved seller
    verification in Flow 2B (see _route_after_own_choice_verification) —
    pure calculation, ZERO LLM calls. Uses 80% LTV (vs LAP's 65%) and caps
    the loan by the customer-stated purchase price as well as the bank's
    own valuation. Unconditionally chains into risk assessment next, same
    as the LAP path (see the plain edge in the graph wiring below)."""
    property_result = state.get("property_verification_result") or {}

    result = valuate_property(
        area_sqft=property_result.get("area_sqft") or 0,
        address=property_result.get("address") or "",
        property_type=property_result.get("property_type") or "residential_apartment",
        registration_number=property_result.get("registration_number") or "",
        government_value=property_result.get("government_value") or 0,
        ltv_ratio=0.80,
        purchase_price=state.get("own_choice_price"),
    )

    prior_reply = state.get("reply") or ""
    combined_reply = f"{prior_reply}\n\n{result['summary']}" if prior_reply else result["summary"]

    return _make_node_output(
        state, combined_reply, "valuation_result", "property_valuation", "own_choice_valuation_agent",
        metadata={"valuation_result": result},
        customer_profile=state.get("customer_profile"),
        valuation_result=result,
    )


def _risk_assessment_node(state: ChatState) -> dict:
    """Reached only by being chained directly after an approved property
    verification, in the SAME turn (see _route_after_verification) — so
    `state["reply"]` at this point is exactly the verification summary the
    previous node just produced, and we prepend it to build one combined
    message. Pulls live risk signals for whichever customer is
    authenticated this session — nothing hardcoded."""
    session_id = state.get("session_id", "")
    user_context = state.get("user_context") or {}
    customer_id = user_context.get("customer_id")

    if customer_id:
        result = assess_risk(customer_id)
    else:
        result = {
            "risk_level": "high", "risk_score": 100, "approved": False,
            "risk_flags": ["missing_customer_id"], "monthly_income": 0,
            "total_existing_emi": 0, "foir": 0,
            "summary": "❌ Could not run risk assessment — missing customer information.",
        }

    mark_step(session_id, "risk", "completed" if result["approved"] else "failed")

    next_stage = "credit_assessment" if result["approved"] else "general"
    prior_reply = state.get("reply") or ""
    combined_reply = f"{prior_reply}\n\n{result['summary']}" if prior_reply else result["summary"]

    return _make_node_output(
        state, combined_reply, "text", next_stage, "risk_assessment_agent",
        metadata={"valuation_result": state.get("valuation_result")},
        customer_profile=state.get("customer_profile"),
        risk_assessment_result=result,
    )


def _credit_assessment_node(state: ChatState) -> dict:
    """Reached only by being chained directly after an approved risk
    assessment, in the SAME turn (see _route_after_risk) — prepends
    whatever combined message has built up so far. Pulls the live CIBIL
    score and affordability for whichever customer is authenticated this
    session — nothing hardcoded. On approval, chains straight into
    _loan_decision_node (see _route_after_credit); on failure, this is
    terminal and the user just sees the rejection summary."""
    session_id = state.get("session_id", "")
    user_context = state.get("user_context") or {}
    customer_id = user_context.get("customer_id")
    valuation_result = state.get("valuation_result") or {}
    # Unified across both LAP (65% LTV) and own-choice (80% LTV, capped by
    # purchase price) flows — valuate_property() always populates "max_loan"
    # at whichever ltv_ratio it was called with.
    max_loan = valuation_result.get("max_loan") or 0

    if customer_id:
        # Factor in any EMI from a loan approved earlier in this browser
        # session (keyed by customer_id in session_store so it persists
        # across New Application clicks, unlike the MemorySaver checkpoint).
        approved_emi = get_customer_approved_emi(customer_id)
        result = assess_credit(customer_id, max_loan, approved_session_emi=approved_emi)
    else:
        result = {
            "approved": False, "cibil_score": None, "cibil_rating": "Poor",
            "max_loan_by_income": 0, "final_loan_eligible": 0, "interest_rate": None,
            "tenure_years": 20, "monthly_emi_estimate": 0,
            "summary": "❌ Could not run credit assessment — missing customer information.",
        }

    mark_step(session_id, "credit", "completed" if result.get("approved") else "failed")

    # Sync the assessment's CIBIL score (from mock_cibil_api) into
    # session_store so /session/status — and therefore the frontend
    # sidebar's credit-score card — shows the SAME number and rating as
    # the loan decision card, not a separately derived value.
    if result.get("cibil_score"):
        set_credit(session_id, result["cibil_score"], result.get("cibil_rating") or "Fair")

    prior_reply = state.get("reply") or ""
    combined_reply = f"{prior_reply}\n\n{result['summary']}" if prior_reply else result["summary"]

    return _make_node_output(
        state, combined_reply, "text", "general", "credit_assessment_agent",
        metadata={"valuation_result": state.get("valuation_result")},
        customer_profile=state.get("customer_profile"),
        credit_assessment_result=result,
    )


def _loan_decision_node(state: ChatState) -> dict:
    """Reached only by being chained directly after an approved credit
    assessment, in the SAME turn (see _route_after_credit). Aggregates
    property + risk + credit into one final decision and emits the
    LOAN_DECISION_CARD: payload the frontend renders as a card — this
    reply intentionally does NOT prepend the prior combined text, so the
    message content starts exactly with that prefix."""
    session_id = state.get("session_id", "")
    user_context = state.get("user_context") or {}
    full_name = user_context.get("full_name") or "Customer"

    property_result = state.get("property_verification_result") or {}
    risk_result = state.get("risk_assessment_result") or {}
    credit_result = state.get("credit_assessment_result") or {}
    flow_type = state.get("flow_type") or "lap"

    decision_result = make_loan_decision(
        property_result, risk_result, credit_result, full_name,
        flow_type=flow_type,
        purchase_price=state.get("own_choice_price"),
    )

    mark_step(session_id, "decision", "completed")

    # If this application was approved, record its monthly EMI so that a
    # subsequent credit assessment in the same browser session (new session_id
    # but same customer_id) can factor it in as an additional obligation.
    if decision_result.get("decision") == "approved":
        customer_id = user_context.get("customer_id")
        if customer_id:
            approved_emi = credit_result.get("monthly_emi_estimate") or 0
            set_customer_approved_emi(customer_id, approved_emi)

    # Offer personalised financial advice as the next step. The offer is
    # carried in metadata/options (NOT appended to the reply text — the
    # frontend JSON.parses everything after the LOAN_DECISION_CARD: prefix,
    # so extra text would break the card). Stage moves to
    # "awaiting_advisor_decision" so the Yes/No answer routes instantly.
    return _make_node_output(
        state, decision_result["summary"], "loan_decision", "awaiting_advisor_decision",
        "loan_decision_agent",
        options=POST_DECISION_ADVICE_OPTIONS,
        metadata={
            "valuation_result": state.get("valuation_result"),
            "post_decision_advice_prompt": POST_DECISION_ADVICE_PROMPT,
        },
        customer_profile=state.get("customer_profile"),
        loan_decision_result=decision_result,
        display_card=decision_result.get("display_card"),
    )


# ---------------------------------------------------------------------------
# Manual-review appointment booking
# ---------------------------------------------------------------------------

APPOINTMENT_YES_PATTERNS = [
    "yes", "book", "appointment", "sure", "okay", "ok",
    "please", "want to", "schedule", "fix", "arrange", "ya", "yep", "yup",
]
APPOINTMENT_NO_PATTERNS = [
    "no", "later", "not now", "maybe", "skip", "cancel",
    "dont", "don't", "nope", "nah",
]
APPOINTMENT_QUESTION_WORDS = (
    "what", "why", "how", "when", "where", "who", "which", "can", "is", "are", "does", "do",
)


def _appointment_decision_node(state: ChatState) -> dict:
    """Detects yes/no/question intent for the manual-review appointment
    offer — instant, no LLM call for the yes/no/default branches. Works
    for any customer's message text, nothing hardcoded."""
    message = state["message"]
    message_lower = message.strip().lower()

    if any(p in message_lower for p in APPOINTMENT_YES_PATTERNS):
        reply = "Great! Please fill in your appointment details below."
        return _make_node_output(
            state, reply, "appointment_form", "awaiting_appointment_form", "appointment_decision_agent",
            customer_profile=state.get("customer_profile"),
        )

    if any(p in message_lower for p in APPOINTMENT_NO_PATTERNS):
        reply = (
            "No problem. You can book an appointment anytime by typing "
            "'book appointment'. Our team will also reach out to you within 2 business days."
        )
        return _make_node_output(
            state, reply, "text", "general", "appointment_decision_agent",
            customer_profile=state.get("customer_profile"),
        )

    is_question = "?" in message_lower or message_lower.startswith(APPOINTMENT_QUESTION_WORDS)
    if is_question:
        answer, scored_docs = faq_agent(message, state.get("chat_history", []))
        combined = answer + "\n\nWould you still like to book an appointment with our property verification team?"
        return _make_node_output(
            state, combined, "text", "awaiting_appointment_decision", "appointment_decision_agent",
            sources=scored_docs,
            customer_profile=state.get("customer_profile"),
        )

    reply = (
        "I didn't quite catch that. Would you like to book an appointment with our "
        "verification team? Please say Yes or No."
    )
    return _make_node_output(
        state, reply, "text", "awaiting_appointment_decision", "appointment_decision_agent",
        customer_profile=state.get("customer_profile"),
    )


def _appointment_booked_node(state: ChatState) -> dict:
    """The frontend sends this immediately after a successful booking via
    the dedicated /appointments/book endpoint — purely a chat-log
    notification, instant ack, no LLM call."""
    message = state["message"]
    match = re.search(r"\{.*\}", message, re.DOTALL)
    try:
        data = json.loads(match.group(0)) if match else {}
    except Exception:
        data = {}

    reply = "Your appointment is confirmed! Our property verification team will be in touch beforehand."
    return _make_node_output(
        state, reply, "text", "general", "appointment_agent",
        customer_profile=state.get("customer_profile"),
        appointment_booked=True,
        appointment_data=data,
    )


def _cancel_appointment_node(state: ChatState) -> dict:
    """Triggered by 'cancel appointment' intent — detected by keyword
    match in _route_after_entry, never left to the LLM router. Instant, no
    LLM call. Looks up whether this session actually has an active
    (non-cancelled) appointment before asking for confirmation, so we
    never ask the user to confirm cancelling something that doesn't
    exist."""
    session_id = state.get("session_id", "")
    appointment = get_appointment(session_id)

    if not appointment or appointment.get("status") == "cancelled":
        reply = "You don't have an active appointment to cancel."
        return _make_node_output(
            state, reply, "text", "general", "cancel_appointment_agent",
            customer_profile=state.get("customer_profile"),
        )

    reply = (
        f"You have an appointment on {appointment.get('appointment_date')} at "
        f"{appointment.get('appointment_time')} ({appointment.get('branch')}). "
        "Are you sure you want to cancel it? Please say Yes or No."
    )
    return _make_node_output(
        state, reply, "text", "awaiting_cancel_confirmation", "cancel_appointment_agent",
        customer_profile=state.get("customer_profile"),
        pending_cancel_appointment_id=appointment.get("id"),
    )


def _cancel_appointment_decision_node(state: ChatState) -> dict:
    """Instant, no LLM — yes/no confirmation for the cancellation asked by
    _cancel_appointment_node. On 'yes' this actually calls
    cancel_appointment() against the database (real cancellation, not just
    a claim); on 'no' the appointment is left untouched."""
    message_lower = state["message"].strip().lower()
    appointment_id = state.get("pending_cancel_appointment_id")

    if any(p in message_lower for p in APPOINTMENT_YES_PATTERNS):
        if not appointment_id:
            reply = "Sorry, I couldn't find that appointment anymore. Please try again."
            return _make_node_output(
                state, reply, "text", "general", "cancel_appointment_agent",
                customer_profile=state.get("customer_profile"),
            )
        updated = cancel_appointment(appointment_id)
        reply = (
            "Your appointment has been cancelled."
            if updated else
            "Sorry, I couldn't cancel your appointment right now. Please try again or contact support."
        )
        return _make_node_output(
            state, reply, "text", "general", "cancel_appointment_agent",
            customer_profile=state.get("customer_profile"),
            pending_cancel_appointment_id=None,
        )

    if any(p in message_lower for p in APPOINTMENT_NO_PATTERNS):
        reply = "No problem — your appointment is still active."
        return _make_node_output(
            state, reply, "text", "general", "cancel_appointment_agent",
            customer_profile=state.get("customer_profile"),
            pending_cancel_appointment_id=None,
        )

    reply = "I didn't quite catch that. Would you like to cancel your appointment? Please say Yes or No."
    return _make_node_output(
        state, reply, "text", "awaiting_cancel_confirmation", "cancel_appointment_agent",
        customer_profile=state.get("customer_profile"),
    )


def _address_confirm_doc_node(state: ChatState) -> dict:
    """User chose 'Document is correct' during the Flow 2B address-mismatch
    prompt — instant, no LLM.  Updates own_choice_address to the address
    found in the document, then runs seller verification immediately in the
    same turn so the user doesn't have to re-submit anything."""
    data = state.get("pending_property_data") or {}
    doc_address = data.get("address") or ""

    # Proceed with verification using the document's address as authoritative
    result = verify_seller_property(
        registration_number=data.get("registration_number"),
        seller_name=data.get("owner_name"),
        address=doc_address,
        area_sqft=data.get("area_sqft"),
    )

    session_id = state.get("session_id", "")
    mark_step(session_id, "property", "completed" if result["verified"] else "failed")

    if result.get("status") == "manual_review":
        reply = (
            result["summary"]
            + "\n\nWould you like to book an appointment with our property "
              "verification team to resolve this?"
        )
        return _make_node_output(
            state, reply, "manual_review_appointment", "awaiting_appointment_decision",
            "own_choice_verification_agent",
            customer_profile=state.get("customer_profile"),
            property_data=data,
            property_verification_result=result,
            own_choice_address=doc_address,
            pending_property_data=None,
        )

    next_stage = "property_valuation" if result["verified"] else "general"
    return _make_node_output(
        state, result["summary"], "text", next_stage,
        "own_choice_verification_agent",
        customer_profile=state.get("customer_profile"),
        property_data=data,
        property_verification_result=result,
        own_choice_address=doc_address,
        pending_property_data=None,
    )


def _address_reenter_node(state: ChatState) -> dict:
    """User chose to re-enter the address during the Flow 2B
    address-mismatch prompt — instant, no LLM.  Clears the pending
    property data and sends the user back to the address-collection step."""
    return _make_node_output(
        state, OWN_CHOICE_ADDRESS_PROMPT, "text", "awaiting_own_choice_address",
        "own_choice_agent",
        flow_type="own_choice",
        customer_profile=state.get("customer_profile"),
        pending_property_data=None,
    )


def _property_followup_node(state: ChatState) -> dict:
    message = state["message"]
    lower = message.lower().strip()
    session_id = state.get("session_id", "")
    shown_properties = state.get("shown_properties", [])
    selected_property_id = state.get("selected_property_id")

    # 1. Handle "continue with this" — the tie-ups selection confirmation.
    # Routing normally sends this straight to the tie_ups_selected node; this
    # branch is a safety net in case the LLM router lands here instead.
    if lower == "continue with this" or lower == "continue" or lower == "proceed":
        return _tie_ups_selected_node(state)

    # 2. Handle database location question
    if lower == "where is the property database located?" or (
        "where" in lower and "database" in lower and ("property" in lower or "properties" in lower)
    ):
        reply = "The property database is located at `backend/mock_data/properties.json`."
        return _make_node_output(
            state, reply, "text", "inventory_flow", "property_followup_agent",
            selected_property_id=selected_property_id,
            shown_properties=shown_properties,
            customer_profile=state.get("customer_profile")
        )

    # Load all inventory properties
    inventory = _load_bank_inventory()

    # 3. Detect property selection in the user's message
    match = re.search(r'\b(binv\d{3})\b', lower)
    if match:
        selected_id = match.group(1).upper()
        if selected_id in inventory:
            selected_property_id = selected_id
            prop = inventory[selected_id]
            # Format numbers as Indian currency
            price_formatted = format_indian_currency(prop["listed_price"])
            dp_formatted = format_indian_currency(prop["down_payment_min"])
            loan_formatted = format_indian_currency(prop["max_loan_available"])
            
            # Construct description
            reply = (
                f"{selected_id} is a {prop['bedrooms']}-bedroom flat at {prop['address']}, "
                f"with an area of {prop['area_sqft']} sqft. The listed price is ₹{price_formatted}, "
                f"minimum down payment is ₹{dp_formatted}, and maximum loan available is ₹{loan_formatted}. "
                f"Let me know if you need more details or wish to proceed."
            )
            
            # Show other properties
            other_props = []
            for pid, pdata in inventory.items():
                if pid != selected_id:
                    other_props.append({
                        "property_id": pid,
                        "address": pdata["address"],
                        "city": pdata["city"],
                        "area_sqft": pdata["area_sqft"],
                        "bedrooms": pdata["bedrooms"],
                        "listed_price": pdata["listed_price"],
                        "down_payment_min": pdata["down_payment_min"],
                        "max_loan_available": pdata["max_loan_available"],
                        "property_score": pdata["property_score"],
                        "nearby_schools": pdata.get("nearby_schools"),
                        "hospitals": pdata.get("hospitals"),
                        "transit": pdata.get("transit"),
                        "crime_rate": pdata.get("crime_rate"),
                    })
            
            options = [{"id": "continue", "label": "Continue with this"}]
            return _make_node_output(
                state, reply, "property_list", "inventory_flow", "property_followup_agent",
                options=options,
                properties=other_props,
                selected_property_id=selected_property_id,
                shown_properties=shown_properties,
                customer_profile=state.get("customer_profile")
            )

    # 4. Handle follow-up Q&A for selected property
    if selected_property_id and selected_property_id in inventory:
        prop = inventory[selected_property_id]
        try:
            resp = _client.chat.completions.create(
                model=CHAT_DEPLOYMENT,
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are Arjun, a senior relationship manager at a reputed Indian bank.

The customer has selected the following property from our bank inventory:
{json.dumps(prop, indent=2)}

They are now asking a question about it (e.g., location, connectivity, crime rate, nearby schools, amenities, pricing, etc.).

Guidelines:
- Use the provided property JSON data for property-specific details (e.g. address, amenities, crime_rate, transit, nearby_schools, hospitals, listed_price).
- Answer questions about nearby schools, hospitals, local connectivity, transit options (metro lines, bus, train), and crime rate by directly using the provided fields (`nearby_schools`, `hospitals`, `transit`, `crime_rate`). Translate these into clear, friendly qualitative explanations.
- Be highly concise, direct, and professional — similar to ChatGPT or Claude.
- Limit responses to 2-3 sentences.
- Don't use markdown tables — plain conversational text only."""
                    },
                    *state.get("chat_history", [])[-6:],
                    {"role": "user", "content": message},
                ],
                temperature=0.3,
            )
            answer = resp.choices[0].message.content
        except Exception as e:
            answer = f"Sorry, I had trouble pulling that up: {e}"

        options = [{"id": "continue", "label": "Continue with this"}]
        return _make_node_output(
            state, answer, "text", "inventory_flow", "property_followup_agent",
            options=options,
            selected_property_id=selected_property_id,
            shown_properties=shown_properties,
            customer_profile=state.get("customer_profile")
        )

    # Fallback to general shown properties
    shown = shown_properties
    try:
        resp = _client.chat.completions.create(
            model=CHAT_DEPLOYMENT,
            messages=[
                {"role": "system", "content": PROPERTY_QA_SYSTEM_PROMPT.format(
                    properties_json=json.dumps(shown, indent=2)
                )},
                *state.get("chat_history", [])[-6:],
                {"role": "user", "content": message},
            ],
            temperature=0.3,
        )
        answer = resp.choices[0].message.content
    except Exception as e:
        answer = f"Sorry, I had trouble pulling that up: {e}"

    return _make_node_output(
        state, answer,
        "property_list" if shown else "text",
        "inventory_flow", "property_followup_agent",
        properties=shown if shown else None,
        selected_property_id=selected_property_id,
        shown_properties=shown,
        customer_profile=state.get("customer_profile")
    )


# Stage-specific nudge appended to FAQ answers given mid-flow, so the
# customer is reminded what we're still waiting on rather than the
# conversation silently dropping the thread they were on.
FAQ_STAGE_REMINDERS = {
    "property_document_requested": "\n\n📎 Reminder: I still need your documents to proceed. Please upload when ready.",
    "awaiting_acquisition_type": "\n\n💬 When ready, please let me know how you acquired your property.",
    "awaiting_property_choice": "\n\n🏠 You were selecting a property — shall we continue?",
    "awaiting_own_choice_address": "\n\n📍 Please share the property address to continue.",
    "awaiting_own_choice_price": "\n\n💰 Please share the approximate purchase price to continue.",
}


def _faq_node(state: ChatState) -> dict:
    message = state["message"]
    lower = message.lower().strip()

    if lower == "where is the property database located?" or (
        "where" in lower and "database" in lower and ("property" in lower or "properties" in lower)
    ):
        reply = "The property database is located at `backend/mock_data/properties.json`."
        return _output(message, reply, "text")

    answer, scored_docs = faq_agent(message, state.get("chat_history", []))

    stage = state.get("stage", "general")
    active_stages = (
        "awaiting_property_choice", "awaiting_tie_up_choice", "inventory_flow", "lap_flow", "own_choice",
        "awaiting_own_choice_address", "awaiting_own_choice_price",
    )
    reminder = FAQ_STAGE_REMINDERS.get(stage, "")

    if stage in active_stages:
        workflow_res = resume_workflow(state)
        combined_reply = answer + "\n\n" + workflow_res["reply"] + reminder

        return _make_node_output(
            state, combined_reply, workflow_res["response_type"], stage, "faq_agent",
            options=workflow_res.get("options"),
            properties=workflow_res.get("properties"),
            doc_type=workflow_res.get("doc_type"),
            sources=scored_docs,
            selected_property_id=state.get("selected_property_id"),
            shown_properties=state.get("shown_properties"),
            customer_profile=state.get("customer_profile")
        )

    return _make_node_output(
        state, answer + reminder, "text", stage, "faq_agent",
        sources=scored_docs,
        customer_profile=state.get("customer_profile")
    )


# ---------------------------------------------------------------------------
# Account / loan-status queries — answered with the customer's REAL data
# ---------------------------------------------------------------------------

def _get_account_summary(customer_id: str) -> dict:
    """Pulls the customer's live account, income, and loan data from the
    database — works for any authenticated customer, nothing hardcoded."""
    from database.init_db import get_connection
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT full_name, account_numbers, monthly_income, avg_monthly_balance,
                   customer_segment, employer_name
            FROM bank_customers WHERE customer_id = ?
            """,
            (customer_id,),
        )
        row = cursor.fetchone()

        cursor.execute(
            """
            SELECT loan_id, loan_type, outstanding_amount, emi, next_emi_date, status
            FROM existing_loans WHERE customer_id = ?
            """,
            (customer_id,),
        )
        loans = [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()

    profile = dict(row) if row else {}
    raw_accounts = profile.get("account_numbers") or ""
    try:
        accounts = json.loads(raw_accounts) if raw_accounts else []
        if not isinstance(accounts, list):
            accounts = [str(accounts)]
    except Exception:
        accounts = [a.strip() for a in raw_accounts.split(",") if a.strip()]

    return {"profile": profile, "accounts": accounts, "loans": loans}


def _account_query_node(state: ChatState) -> dict:
    """Answers questions about the customer's own bank accounts, existing
    loans, EMIs, and disbursement — grounded in their real database rows
    plus any loan approved earlier in this session. LLM phrases the answer
    to the user's specific question; falls back to a plain data summary if
    the LLM call fails. Stage is left untouched so any in-progress flow
    resumes naturally afterwards."""
    message = state["message"]
    stage = state.get("stage", "general")
    user_context = state.get("user_context") or {}
    customer_id = user_context.get("customer_id")

    if not customer_id:
        return _make_node_output(
            state, "Please log in so I can look up your account details.",
            "text", stage, "account_query_agent",
            customer_profile=state.get("customer_profile"),
        )

    data = _get_account_summary(customer_id)
    profile = data["profile"]
    accounts = data["accounts"]
    loans = data["loans"]

    sb_accounts = [a for a in accounts if not str(a).upper().startswith("FD")]
    fd_accounts = [a for a in accounts if str(a).upper().startswith("FD")]

    loan_lines = "\n".join(
        f"  - {l.get('loan_type', 'Loan')} (ID {l.get('loan_id', '?')}): "
        f"EMI Rs.{(l.get('emi') or 0):,.0f}/month, "
        f"Outstanding Rs.{(l.get('outstanding_amount') or 0):,.0f}, "
        f"Status: {l.get('status', 'active')}"
        for l in loans
    ) if loans else "  No existing loans on record."

    decision_result = state.get("loan_decision_result") or {}
    card = decision_result.get("display_card") or {}
    if card:
        session_loan = (
            f"Decision: {str(card.get('decision', 'N/A')).upper()}\n"
            f"Approved Amount: Rs.{(card.get('loan_amount') or 0):,.0f}\n"
            f"Interest Rate: {card.get('interest_rate', '—')}%\n"
            f"Monthly EMI: Rs.{(card.get('monthly_emi') or 0):,.0f}"
        )
    else:
        session_loan = "No loan application decided in this session yet."

    system_prompt = f"""You are Arjun, a helpful relationship manager at National Bank.
You have full access to this customer's bank data.
Answer their specific question using real numbers.
NEVER say you don't have access to account details.

Customer: {profile.get('full_name', 'Customer')}
Savings Accounts: {', '.join(str(a) for a in sb_accounts) if sb_accounts else 'None on record'}
Fixed Deposits: {', '.join(str(a) for a in fd_accounts) if fd_accounts else 'None on record'}
Average Monthly Balance: Rs.{(profile.get('avg_monthly_balance') or 0):,.0f}
Monthly Income: Rs.{(profile.get('monthly_income') or 0):,.0f}
Employer: {profile.get('employer_name') or 'Not on record'}
Active Loans: {loan_lines}
Customer Segment: {profile.get('customer_segment') or 'standard'}

THIS SESSION'S LOAN APPLICATION
{session_loan}

GUIDELINES
- Answer the question directly and specifically in 2-4 sentences, using
  ONLY the real data above — never invent figures or account numbers.
- For "when will I get the money" / disbursement questions: after final
  approval and document submission, disbursement typically takes 7-10
  working days, credited to their savings account (name the actual account
  number if one exists).
- For "which account" questions: state their actual account numbers.
- Use Rs. for all amounts with the real figures above."""

    try:
        resp = _client.chat.completions.create(
            model=CHAT_DEPLOYMENT,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
            max_tokens=250,
            temperature=0.3,
        )
        reply = resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"Account query LLM failed: {e}")
        reply = (
            f"Here's what I have on file for you:\n\n"
            f"**Accounts:** {', '.join(str(a) for a in accounts) if accounts else 'None on record'}\n"
            f"**Existing loans:**\n{loan_lines}\n\n"
            + (
                f"**This session:** loan {str(card.get('decision', '')).upper()} — "
                f"₹{(card.get('loan_amount') or 0):,.0f} at {card.get('interest_rate', '—')}%, "
                f"EMI ₹{(card.get('monthly_emi') or 0):,.0f}/month."
                if card else "No loan application decided in this session yet."
            )
        )

    # Preserve whatever stage the customer was at — never reset to
    # "awaiting_property_choice" or re-show the property-choice buttons.
    # At the start of the flow, just append a gentle loan-application nudge.
    if stage in ("awaiting_property_choice", "new"):
        reply += (
            "\n\nIs there anything else I can help you with "
            "regarding your loan application?"
        )

    return _make_node_output(
        state, reply, "text", stage, "account_query_agent",
        customer_profile=state.get("customer_profile"),
    )


# ---------------------------------------------------------------------------
# Financial advisor in main chat
# ---------------------------------------------------------------------------

def _financial_advisor_node(state: ChatState) -> dict:
    """Routes the customer's question to the LLM financial advisor with
    their full live financial context plus this session's loan decision.
    Reached via the post-decision "Yes, help me" button or financial-advice
    keywords typed at any stage. Sets stage to "financial_advisor" so every
    follow-up message keeps going to the advisor until a loan-flow route
    takes over. Works for any customer — nothing hardcoded."""
    message = state["message"]
    lower = message.strip().lower()
    user_context = state.get("user_context") or {}
    customer_id = user_context.get("customer_id")

    if not customer_id:
        return _make_node_output(
            state,
            "Please log in so I can access your financial profile and give personalised advice.",
            "text", state.get("stage", "general"), "financial_advisor_agent",
            customer_profile=state.get("customer_profile"),
        )

    if lower in ADVISOR_YES_LABELS:
        advisor_message = (
            "Please give me personalised financial recommendations based on my "
            "current financial situation and my recent loan decision."
        )
    else:
        advisor_message = message

    reply = get_financial_advice(
        customer_id,
        advisor_message,
        state.get("chat_history", []),
        state.get("loan_decision_result"),
    )

    return _make_node_output(
        state, reply, "text", "financial_advisor", "financial_advisor_agent",
        customer_profile=state.get("customer_profile"),
    )


def _advisor_decline_node(state: ChatState) -> dict:
    """User clicked "No, thanks" on the post-decision advisor offer —
    instant, no LLM call."""
    return _make_node_output(
        state, "No problem! Feel free to ask me for financial advice anytime.",
        "text", "general", "financial_advisor_agent",
        customer_profile=state.get("customer_profile"),
    )


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def _route_entry(state: ChatState) -> str:
    # Hard stop, checked before ANY other logic: once this session has
    # produced an approved loan decision, every subsequent message — no
    # matter what the user typed or clicked — gets the same "already
    # approved" notice instead of being routed anywhere else. New
    # Application rotates session_id to a fresh thread with no
    # checkpointed loan_decision_result, which is what clears this.
    decision_result = state.get("loan_decision_result")
    if decision_result and decision_result.get("decision") == "approved":
        # Post-decision follow-ups are the one exception: the advisor
        # yes/no answer, an ongoing advisor conversation, or an account /
        # loan-status / financial-advice question should still be answered
        # rather than met with the "already approved" wall.
        message = state.get("message", "")
        lower = message.strip().lower()
        is_followup = (
            state.get("stage") in ("awaiting_advisor_decision", "financial_advisor")
            or lower in ADVISOR_YES_LABELS
            or lower in ADVISOR_NO_LABELS
            or _matches_keywords(message, ACCOUNT_QUERY_KEYWORDS)
            or _matches_keywords(message, FINANCIAL_ADVISOR_KEYWORDS)
        )
        if is_followup and state.get("user_context") is not None:
            return "authed"
        return "loan_already_approved"
    if state.get("user_context") is not None:
        return "authed"
    if is_awaiting_documents(state.get("session_id", "")):
        return "kyc"
    return "guest"


def _route_stage_label(message: str, stage: str) -> str:
    """LLM call → one of: lap, home_loan, property_followup, faq"""
    try:
        resp = _client.chat.completions.create(
            model=CHAT_DEPLOYMENT,
            messages=[
                {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                {"role": "user", "content": f"Current stage: {stage}\nMessage: {message}"},
            ],
            temperature=0,
            max_tokens=10,
        )
        label = resp.choices[0].message.content.strip().lower()
        if label not in ("lap", "home_loan", "property_followup", "faq"):
            return "faq"
        return label
    except Exception:
        return "faq"


INSTANT_ROUTES = {
    "i own a property": ("lap_flow", "acquisition_type"),
    "i want to buy a property": ("home_loan", "home_loan_choice"),  
    "i purchased it": ("awaiting_acquisition_type", "set_document_requirements"),
    "i inherited it": ("awaiting_acquisition_type", "set_document_requirements"),
    "it was gifted to me": ("awaiting_acquisition_type", "set_document_requirements"),
    "our tie-ups": ("home_loan", "tie_ups"),
    "my own choice": ("own_choice", "own_choice"),
    "yes, help me": ("awaiting_advisor_decision", "financial_advisor"),
    # Flow 2A tie-ups pipeline buttons — stage-strict (see below) so e.g.
    # "check eligibility" typed in an unrelated flow falls through to
    # normal routing instead of hijacking the turn.
    "continue with this": ("inventory_flow", "tie_ups_selected"),
    "check eligibility": ("tie_ups_property_selected", "tie_ups_eligibility"),
    "check my eligibility": ("tie_ups_property_selected", "tie_ups_eligibility"),
    "ask property": ("tie_ups_property_selected", "tie_ups_property_qa"),
}

# Keys in INSTANT_ROUTES that only fire when the persisted stage matches the
# expected one — all other keys route regardless of stage (button clicked
# from an older turn should still work).
_STAGE_STRICT_ROUTES = {
    "continue with this", "check eligibility", "check my eligibility", "ask property",
}

def _should_fast_route(message: str, stage: str) -> str | None:
    key = message.strip().lower()
    if key in INSTANT_ROUTES:
        expected_stage, target_node = INSTANT_ROUTES[key]
        if key in _STAGE_STRICT_ROUTES and stage != expected_stage:
            return None
        # Allow if stage matches OR stage is close enough
        return target_node
    return None


def _route_after_entry(state: ChatState) -> str:
    # First touch after login already produced the MCQ — terminal.
    if state.get("just_handled"):
        return "end"

    stage = state.get("stage", "general")
    message = state["message"]

    # Account / loan-status / EMI / disbursement questions — the very
    # first check after authentication, BEFORE any stage handling or FAQ
    # routing, so no other node can intercept them with a generic "I don't
    # have access" answer. Answered with the customer's REAL database data.
    if _matches_keywords(message, ACCOUNT_QUERY_KEYWORDS):
        return "account_query"

    # Check fast path before any LLM call
    fast_node = _should_fast_route(message, stage)
    if fast_node is not None:
        return fast_node

    # Own-choice instant flow — must NEVER go through LLM router.
    if stage == "own_choice":
        return "own_choice_address"
    if stage == "awaiting_own_choice_address":
        return "own_choice_price"
    if stage == "awaiting_own_choice_price":
        return "own_choice_price_parser"

    # Flow 2A tie-ups: a property has been selected — either the customer
    # proceeds to the eligibility check (button or a plain "yes"), or
    # anything else is treated as a question about the selected property.
    if stage == "tie_ups_property_selected":
        tie_lower = message.strip().lower()
        if tie_lower in TIE_UPS_ELIGIBILITY_YES:
            return "tie_ups_eligibility"
        return "tie_ups_property_qa"

    # Appointment cancellation confirmation — instant, no LLM.
    if stage == "awaiting_cancel_confirmation":
        return "cancel_appointment_decision"

    # Flow 2B address-mismatch confirmation — instant, no LLM.
    if stage == "awaiting_address_confirmation":
        msg_lower = message.lower()
        if "document is correct" in msg_lower:
            return "address_confirm_doc"
        return "address_reenter"

    lower = message.lower().strip()

    # 0. Property pipeline — always wins over everything else below.
    # The document confirm-and-proceed card sends back the extracted
    # fields as a PROPERTY_DATA: registration_number-bearing JSON payload,
    # regardless of whatever stage we're currently in. Verification and
    # risk assessment (and credit, if risk approves) all auto-chain in the
    # same turn from here — see _route_after_verification / _route_after_risk.
    if message.strip().startswith("PROPERTY_DATA:") or "registration_number" in message:
        if state.get("flow_type") == "own_choice":
            return "own_choice_verification"
        return "property_verification"

    # Post-decision advisor offer — instant yes/no detection, no LLM.
    # Anything that isn't a clear yes/no falls through to normal routing
    # (so an account/advice question asked here still gets answered).
    if stage == "awaiting_advisor_decision":
        if lower in ADVISOR_YES_LABELS or lower in ("yes", "sure", "okay", "ok", "yes please"):
            return "financial_advisor"
        if lower in ADVISOR_NO_LABELS or lower in ("no", "nope", "not now"):
            return "advisor_decline"

    # "How did you acquire this property?" answer — only steal the turn if
    # the message actually looks like one of the three acquisition choices;
    # otherwise let it fall through to FAQ/LLM routing below (so a genuine
    # question asked at this point still gets answered, with a reminder).
    if stage == "awaiting_acquisition_type" and _detect_acquisition_type(message):
        return "set_document_requirements"

    # Manual-review appointment flow — instant, no LLM. "book appointment"
    # works from ANY stage; the yes/no/question/default detection itself
    # only applies once we're actually mid-flow waiting for that answer.
    if message.strip().startswith("APPOINTMENT_BOOKED:"):
        return "appointment_booked"
    if lower == "book appointment":
        return "appointment_decision"
    if stage == "awaiting_appointment_decision":
        return "appointment_decision"

    # Real appointment cancellation — instant, no LLM. Detected by keyword
    # match rather than left for the LLM to guess at. Checked after the
    # stage=="awaiting_appointment_decision" branch above so a "cancel"
    # typed while confirming a NEW booking is still treated as declining
    # that booking, not as cancelling an existing appointment.
    if "cancel" in lower and "appointment" in lower:
        return "cancel_appointment"

    # 1. Short-circuit routing only for exact matches on UI button labels and property IDs
    if lower == "where is the property database located?":
        return "property_followup"

    # Exact property ID matching (e.g. binv001)
    if re.match(r'^binv\d{3}$', lower):
        return "property_followup"

    # Stage-aware Continue matching — confirming a tie-up property selection.
    if lower == "continue with this" or lower == "continue" or lower == "proceed":
        if stage == "inventory_flow":
            return "tie_ups_selected"

    # Welcome MCQ selections
    if stage == "awaiting_property_choice":
        if lower == "i own a property" or lower == "i own a property (lap)":
            return "lap"
        if lower == "i want to buy a property" or lower == "i want to buy a new property":
            return "home_loan"

    # Tie-up MCQ selections
    if stage == "awaiting_tie_up_choice":
        if lower == "our tie-ups":
            return "show_inventory"
        if lower == "my own choice":
            return "own_choice"

    # Global backup exact match button selectors (in case clicked from older turns)
    if lower in ("i own a property", "i own a property (lap)", "lap"):
        return "lap"
    if lower in ("i want to buy a property", "i want to buy a new property"):
        return "home_loan"
    if lower == "our tie-ups":
        return "show_inventory"
    if lower == "my own choice":
        return "own_choice"
        
    # Yes / No buttons
    if lower == "yes":
        if stage == "awaiting_tie_up_choice":
            return "show_inventory"
    if lower == "no":
        if stage == "awaiting_tie_up_choice":
            return "own_choice"

    # Ongoing financial-advisor conversation: every message keeps going to
    # the advisor UNLESS a loan-flow route already claimed it above.
    if stage == "financial_advisor":
        return "financial_advisor"

    # (Account-query keywords are handled at the very top of this router.)

    # Financial-advice keywords work from ANY stage.
    if _matches_keywords(message, FINANCIAL_ADVISOR_KEYWORDS):
        return "financial_advisor"

    # 2. FALLBACK: Route using LLM classifier
    label = _route_stage_label(message, stage)
    if label == "property_followup" and stage != "inventory_flow":
        label = "faq"
    return label


def _route_after_kyc(state: ChatState) -> str:
    # First touch already sent the document-request message — terminal.
    if state.get("just_handled"):
        return "end"
    return "financial_document"


# ---------------------------------------------------------------------------
# Graph wiring
# ---------------------------------------------------------------------------

_graph = StateGraph(ChatState)
_graph.add_node("loan_already_approved", _loan_already_approved_node)
_graph.add_node("guest", _guest_node)
_graph.add_node("kyc", _kyc_node)
_graph.add_node("financial_document", _financial_document_node)
_graph.add_node("authed_entry", _authed_entry_node)
_graph.add_node("lap", _lap_node)
_graph.add_node("home_loan", _home_loan_node)
_graph.add_node("explain_choice", _explain_choice_node)
_graph.add_node("show_inventory", _show_inventory_node)
_graph.add_node("tie_ups_selected", _tie_ups_selected_node)
_graph.add_node("tie_ups_property_qa", _tie_ups_property_qa_node)
_graph.add_node("tie_ups_eligibility", _tie_ups_eligibility_node)
_graph.add_node("own_choice", _own_choice_node)
_graph.add_node("own_choice_address", _own_choice_address_node)
_graph.add_node("own_choice_price", _own_choice_price_node)
_graph.add_node("own_choice_price_parser", _own_choice_price_parser_node)
_graph.add_node("property_followup", _property_followup_node)
_graph.add_node("faq", _faq_node)
_graph.add_node("property_document_upload", _property_document_upload_node)
_graph.add_node("property_verification", _property_verification_node)
_graph.add_node("property_valuation", _property_valuation_node)
_graph.add_node("own_choice_verification", _own_choice_verification_node)
_graph.add_node("own_choice_valuation", _own_choice_valuation_node)
_graph.add_node("risk_assessment", _risk_assessment_node)
_graph.add_node("acquisition_type", _acquisition_type_node)
_graph.add_node("set_document_requirements", _set_document_requirements_node)
_graph.add_node("credit_assessment", _credit_assessment_node)
_graph.add_node("loan_decision", _loan_decision_node)
_graph.add_node("appointment_decision", _appointment_decision_node)
_graph.add_node("appointment_booked", _appointment_booked_node)
_graph.add_node("cancel_appointment", _cancel_appointment_node)
_graph.add_node("cancel_appointment_decision", _cancel_appointment_decision_node)
_graph.add_node("address_confirm_doc", _address_confirm_doc_node)
_graph.add_node("address_reenter", _address_reenter_node)
_graph.add_node("account_query", _account_query_node)
_graph.add_node("financial_advisor", _financial_advisor_node)
_graph.add_node("advisor_decline", _advisor_decline_node)

_graph.add_conditional_edges(
    START, _route_entry,
    {
        "guest": "guest", "kyc": "kyc", "authed": "authed_entry",
        "loan_already_approved": "loan_already_approved",
    },
)
_graph.add_edge("loan_already_approved", END)
_graph.add_edge("guest", END)
_graph.add_conditional_edges(
    "kyc", _route_after_kyc,
    {"end": END, "financial_document": "financial_document"},
)
_graph.add_edge("financial_document", END)
_graph.add_conditional_edges(
    "authed_entry",
    _route_after_entry,
    {
        "end": END,
        "lap": "lap",
        "home_loan": "home_loan",
        "home_loan_choice": "home_loan",
        "explain_choice": "explain_choice",
        "show_inventory": "show_inventory",
        "tie_ups": "show_inventory",
        "tie_ups_selected": "tie_ups_selected",
        "tie_ups_property_qa": "tie_ups_property_qa",
        "tie_ups_eligibility": "tie_ups_eligibility",
        "own_choice": "own_choice",
        "own_choice_address": "own_choice_address",
        "own_choice_price": "own_choice_price",
        "own_choice_price_parser": "own_choice_price_parser",
        "property_followup": "property_followup",
        "faq": "faq",
        "property_verification": "property_verification",
        "own_choice_verification": "own_choice_verification",
        "set_document_requirements": "set_document_requirements",
        "acquisition_type": "acquisition_type",
        "appointment_decision": "appointment_decision",
        "appointment_booked": "appointment_booked",
        "cancel_appointment": "cancel_appointment",
        "cancel_appointment_decision": "cancel_appointment_decision",
        "address_confirm_doc": "address_confirm_doc",
        "address_reenter": "address_reenter",
        "account_query": "account_query",
        "financial_advisor": "financial_advisor",
        "advisor_decline": "advisor_decline",
    },
)


def _route_after_lap(state: ChatState) -> str:
    """After choosing LAP: ask how they acquired the property before
    requesting documents (required docs differ by acquisition type),
    unless we're already past that (resumed mid-flow)."""
    if state.get("property_data"):
        return "end"
    if state.get("acquisition_type"):
        return "property_document_upload"
    return "acquisition_type"


def _route_after_verification(state: ChatState) -> str:
    """Proactive bot: an approved verification chains straight into
    property valuation in the same turn — the user doesn't have to say
    anything. Valuation itself then unconditionally chains into risk
    assessment (see the plain edge below; valuation has no failure
    branch, it's pure calculation)."""
    result = state.get("property_verification_result") or {}
    if result.get("verified"):
        return "property_valuation"
    return "end"


def _route_after_own_choice_verification(state: ChatState) -> str:
    """Proactive bot: an approved seller verification (Flow 2B) chains
    straight into own-choice valuation in the same turn, mirroring
    _route_after_verification for the LAP flow."""
    result = state.get("property_verification_result") or {}
    if result.get("verified"):
        return "own_choice_valuation"
    return "end"


def _route_after_risk(state: ChatState) -> str:
    """Proactive bot: an approved risk assessment chains straight into
    credit assessment in the same turn."""
    result = state.get("risk_assessment_result") or {}
    if result.get("approved"):
        return "credit_assessment"
    return "end"


def _route_after_credit(state: ChatState) -> str:
    """Proactive bot: an approved credit assessment chains straight into
    the final loan decision in the same turn."""
    result = state.get("credit_assessment_result") or {}
    if result.get("approved"):
        return "loan_decision"
    return "end"


_graph.add_conditional_edges(
    "lap", _route_after_lap,
    {
        "acquisition_type": "acquisition_type",
        "property_document_upload": "property_document_upload",
        "end": END,
    },
)
_graph.add_edge("own_choice", END)
_graph.add_edge("own_choice_address", END)
_graph.add_edge("own_choice_price", END)
_graph.add_edge("own_choice_price_parser", END)
_graph.add_conditional_edges(
    "property_verification", _route_after_verification,
    {"property_valuation": "property_valuation", "end": END},
)
_graph.add_edge("property_valuation", "risk_assessment")
_graph.add_conditional_edges(
    "own_choice_verification", _route_after_own_choice_verification,
    {"own_choice_valuation": "own_choice_valuation", "end": END},
)
_graph.add_edge("own_choice_valuation", "risk_assessment")
# Flow 2A tie-ups: selection and Q&A are terminal for their turn; the
# eligibility node auto-chains straight into the shared risk → credit →
# decision pipeline in the SAME turn, exactly like the valuation nodes.
_graph.add_edge("tie_ups_selected", END)
_graph.add_edge("tie_ups_property_qa", END)
_graph.add_edge("tie_ups_eligibility", "risk_assessment")
_graph.add_conditional_edges(
    "risk_assessment", _route_after_risk,
    {"credit_assessment": "credit_assessment", "end": END},
)
_graph.add_conditional_edges(
    "credit_assessment", _route_after_credit,
    {"loan_decision": "loan_decision", "end": END},
)
_graph.add_edge("acquisition_type", END)
_graph.add_edge("set_document_requirements", END)
_graph.add_edge("loan_decision", END)
_graph.add_edge("appointment_decision", END)
_graph.add_edge("appointment_booked", END)
_graph.add_edge("cancel_appointment", END)
_graph.add_edge("cancel_appointment_decision", END)
# Flow 2B address-mismatch confirmation nodes.
# address_confirm_doc may chain into own_choice_valuation if verification
# approves; address_reenter terminates (the user re-types their address next).
_graph.add_conditional_edges(
    "address_confirm_doc", _route_after_own_choice_verification,
    {"own_choice_valuation": "own_choice_valuation", "end": END},
)
_graph.add_edge("address_reenter", END)
_graph.add_edge("account_query", END)
_graph.add_edge("financial_advisor", END)
_graph.add_edge("advisor_decline", END)
_graph.add_edge("property_document_upload", END)
_graph.add_edge("home_loan", END)
_graph.add_edge("explain_choice", END)
_graph.add_edge("show_inventory", END)
_graph.add_edge("property_followup", END)
_graph.add_edge("faq", END)

_compiled = _graph.compile(checkpointer=MemorySaver())


# ---------------------------------------------------------------------------
# Public entry point — called by main.py's POST /chat
# ---------------------------------------------------------------------------

def is_unsupported_loan(message: str) -> bool:
    lower = message.lower()
    
    # 1. Check exact phrase matches first
    phrases = [
        "car loan", "personal loan", "gold loan", "business loan",
        "education loan", "student loan", "auto loan", "vehicle loan",
        "bike loan", "two wheeler loan", "two-wheeler loan", "motorcycle loan",
        "credit card"
    ]
    if any(phrase in lower for phrase in phrases):
        return True
        
    # 2. Check standalone keywords with word boundaries to avoid false substring matches (e.g. matching "card" as "car")
    unsupported_words = [
        "car", "cars", "bike", "bikes", "motorcycle", "motorcycles",
        "auto", "vehicle", "vehicles", "gold", "education", "student",
        "students", "study", "personal", "business"
    ]
    for word in unsupported_words:
        if re.search(r'\b' + re.escape(word) + r'\b', lower):
            return True
            
    return False


def run_chat_graph(message: str, session_id: str, user_context: Optional[dict]) -> dict:
    # Financial-advice and account questions may legitimately mention words
    # from the unsupported-loan list (e.g. "personal financial advice",
    # "should I invest in gold?") — let those through to the graph.
    is_advice_or_account_query = _matches_keywords(
        message, FINANCIAL_ADVISOR_KEYWORDS
    ) or _matches_keywords(message, ACCOUNT_QUERY_KEYWORDS)

    if is_unsupported_loan(message) and not is_advice_or_account_query:
        return {
            "reply": "Hi there! 👋 I'm Arjun, your dedicated relationship manager. Please note that BankWise AI currently only supports Home Loans and Loans Against Property (LAP). We don't support other loan products (like car, personal, or education loans) at this time, but I'd be glad to assist you with your home loan needs!",
            "type": "text",
            "options": None,
            "properties": None,
            "doc_type": None,
            "sources": None,
            "metadata": None,
        }

    config = {"configurable": {"thread_id": session_id}}
    result = _compiled.invoke(
        {"message": message, "session_id": session_id, "user_context": user_context},
        config=config,
    )
    return {
        "reply": result.get("reply", "Sorry, I couldn't process that response."),
        "type": result.get("response_type", "text"),
        "options": result.get("options"),
        "properties": result.get("properties"),
        "doc_type": result.get("doc_type"),
        "sources": result.get("sources"),
        "metadata": result.get("metadata"),
        "display_card": result.get("display_card"),
    }




