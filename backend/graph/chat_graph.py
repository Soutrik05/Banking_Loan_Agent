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
from session_store import get_session, mark_step
from agents.property_verification_agent import verify_property
from agents.risk_assessment_agent import assess_risk
from agents.credit_assessment_agent import assess_credit
from agents.loan_decision_agent import make_loan_decision
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
        "awaiting_acquisition_type",
        "property_document_requested", "property_verification", "risk_assessment",
        "credit_assessment",
    ]
    shown_properties: list
    selected_property_id: Optional[str]
    just_handled: bool  # set by authed_entry/kyc every turn; True only when the node produced the terminal reply itself

    # LAP property pipeline: Sale Deed fields confirmed by the user, plus the
    # results of the two agent checks that run against them.
    property_data: Optional[dict]
    property_verification_result: Optional[dict]
    risk_assessment_result: Optional[dict]
    credit_assessment_result: Optional[dict]
    loan_decision_result: Optional[dict]

    # "How did you acquire this property?" — determines which documents
    # are required before the property pipeline can proceed.
    acquisition_type: Optional[str]
    required_documents: Optional[list]

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

    if stage == "new":
        if mid_flow_message:
            # Don't touch stage at all — _route_after_entry's
            # registration_number short-circuit routes this correctly to
            # property_verification regardless of whatever stage says.
            return {
                "customer_profile": profile,
                "current_agent": "authed_entry_agent",
                "just_handled": False,
            }
        if is_existing or already_answered:
            # Existing customer (already welcomed/greeted on the frontend), or a
            # fresh thread whose first message is already an answer to the
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
        else:
            # New customer: greeting hasn't been shown yet. Greet them.
            card = get_property_choice_message()
            first_name = (user_context.get("full_name") or "there").split()[0]
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
        customer_profile=state.get("customer_profile")
    )


def _own_choice_node(state: ChatState) -> dict:
    return _make_node_output(
        state, OWN_CHOICE_PROMPT, "text", "own_choice", "own_choice_agent",
        customer_profile=state.get("customer_profile")
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

    match = re.search(r"\{.*\}", message, re.DOTALL)
    try:
        data = json.loads(match.group(0) if match else message)
    except Exception:
        reply = "Sorry, I couldn't read those property details. Please try uploading the document again."
        return _make_node_output(
            state, reply, "text", "general", "property_verification_agent",
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

    next_stage = "risk_assessment" if result["verified"] else "general"

    return _make_node_output(
        state, result["summary"], "text", next_stage, "property_verification_agent",
        customer_profile=state.get("customer_profile"),
        property_data=data,
        property_verification_result=result,
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
    property_result = state.get("property_verification_result") or {}
    max_loan = property_result.get("max_loan_eligible") or 0

    if customer_id:
        result = assess_credit(customer_id, max_loan)
    else:
        result = {
            "approved": False, "cibil_score": None, "cibil_rating": "Poor",
            "max_loan_by_income": 0, "final_loan_eligible": 0, "interest_rate": None,
            "tenure_years": 20, "monthly_emi_estimate": 0,
            "summary": "❌ Could not run credit assessment — missing customer information.",
        }

    mark_step(session_id, "credit", "completed" if result.get("approved") else "failed")

    prior_reply = state.get("reply") or ""
    combined_reply = f"{prior_reply}\n\n{result['summary']}" if prior_reply else result["summary"]

    return _make_node_output(
        state, combined_reply, "text", "general", "credit_assessment_agent",
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

    decision_result = make_loan_decision(property_result, risk_result, credit_result, full_name)

    mark_step(session_id, "decision", "completed")

    return _make_node_output(
        state, decision_result["summary"], "text", "general", "loan_decision_agent",
        customer_profile=state.get("customer_profile"),
        loan_decision_result=decision_result,
    )


def _property_followup_node(state: ChatState) -> dict:
    message = state["message"]
    lower = message.lower().strip()
    session_id = state.get("session_id", "")
    shown_properties = state.get("shown_properties", [])
    selected_property_id = state.get("selected_property_id")

    # 1. Handle "continue with this"
    if lower == "continue with this" or lower == "continue" or lower == "proceed":
        from session_store import mark_step
        mark_step(session_id, "property", "completed")
        mark_step(session_id, "risk", "active", set_active=True)
        return _make_node_output(
            state, "Woho! Great choice!", "text", "general", "property_followup_agent",
            selected_property_id=selected_property_id,
            shown_properties=shown_properties,
            customer_profile=state.get("customer_profile")
        )

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
    active_stages = ("awaiting_property_choice", "awaiting_tie_up_choice", "inventory_flow", "lap_flow", "own_choice")
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
# Routing
# ---------------------------------------------------------------------------

def _route_entry(state: ChatState) -> str:
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
}

def _should_fast_route(message: str, stage: str) -> str | None:
    key = message.strip().lower()
    if key in INSTANT_ROUTES:
        expected_stage, target_node = INSTANT_ROUTES[key]
        # Allow if stage matches OR stage is close enough
        return target_node
    return None


def _route_after_entry(state: ChatState) -> str:
    # First touch after login already produced the MCQ — terminal.
    if state.get("just_handled"):
        return "end"

    stage = state.get("stage", "general")
    message = state["message"]

    # Check fast path before any LLM call
    fast_node = _should_fast_route(message, stage)
    if fast_node is not None:
        return fast_node

    lower = message.lower().strip()

    # 0. Property pipeline — always wins over everything else below.
    # The document confirm-and-proceed card sends back the extracted
    # fields as a PROPERTY_DATA: registration_number-bearing JSON payload,
    # regardless of whatever stage we're currently in. Verification and
    # risk assessment (and credit, if risk approves) all auto-chain in the
    # same turn from here — see _route_after_verification / _route_after_risk.
    if message.strip().startswith("PROPERTY_DATA:") or "registration_number" in message:
        return "property_verification"

    # "How did you acquire this property?" answer — only steal the turn if
    # the message actually looks like one of the three acquisition choices;
    # otherwise let it fall through to FAQ/LLM routing below (so a genuine
    # question asked at this point still gets answered, with a reminder).
    if stage == "awaiting_acquisition_type" and _detect_acquisition_type(message):
        return "set_document_requirements"

    # 1. Short-circuit routing only for exact matches on UI button labels and property IDs
    if lower == "where is the property database located?":
        return "property_followup"

    # Exact property ID matching (e.g. binv001)
    if re.match(r'^binv\d{3}$', lower):
        return "property_followup"

    # Stage-aware Continue matching
    if lower == "continue with this" or lower == "continue" or lower == "proceed":
        if stage == "inventory_flow":
            return "property_followup"

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
_graph.add_node("guest", _guest_node)
_graph.add_node("kyc", _kyc_node)
_graph.add_node("financial_document", _financial_document_node)
_graph.add_node("authed_entry", _authed_entry_node)
_graph.add_node("lap", _lap_node)
_graph.add_node("home_loan", _home_loan_node)
_graph.add_node("explain_choice", _explain_choice_node)
_graph.add_node("show_inventory", _show_inventory_node)
_graph.add_node("own_choice", _own_choice_node)
_graph.add_node("property_followup", _property_followup_node)
_graph.add_node("faq", _faq_node)
_graph.add_node("property_document_upload", _property_document_upload_node)
_graph.add_node("property_verification", _property_verification_node)
_graph.add_node("risk_assessment", _risk_assessment_node)
_graph.add_node("acquisition_type", _acquisition_type_node)
_graph.add_node("set_document_requirements", _set_document_requirements_node)
_graph.add_node("credit_assessment", _credit_assessment_node)
_graph.add_node("loan_decision", _loan_decision_node)

_graph.add_conditional_edges(
    START, _route_entry,
    {"guest": "guest", "kyc": "kyc", "authed": "authed_entry"},
)
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
        "own_choice": "own_choice",
        "property_followup": "property_followup",
        "faq": "faq",
        "property_verification": "property_verification",
        "set_document_requirements": "set_document_requirements",
        "acquisition_type": "acquisition_type",
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


def _route_after_own_choice(state: ChatState) -> str:
    """Buying a new property of their own choice — no 'how did you acquire
    it' question (they don't own it yet); go straight to document upload."""
    if not state.get("property_data"):
        return "property_document_upload"
    return "end"


def _route_after_verification(state: ChatState) -> str:
    """Proactive bot: an approved verification chains straight into risk
    assessment in the same turn — the user doesn't have to say anything."""
    result = state.get("property_verification_result") or {}
    if result.get("verified"):
        return "risk_assessment"
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
_graph.add_conditional_edges(
    "own_choice", _route_after_own_choice,
    {"property_document_upload": "property_document_upload", "end": END},
)
_graph.add_conditional_edges(
    "property_verification", _route_after_verification,
    {"risk_assessment": "risk_assessment", "end": END},
)
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
    if is_unsupported_loan(message):
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
    }




