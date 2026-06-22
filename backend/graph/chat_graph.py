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
    stage: Literal["new", "awaiting_property_choice", "awaiting_tie_up_choice", "lap_flow", "inventory_flow", "general"]
    shown_properties: list
    selected_property_id: Optional[str]
    just_handled: bool  # set by authed_entry/kyc every turn; True only when the node produced the terminal reply itself

    # New-customer, pre-JWT onboarding stage (KYC identity verified, financial
    # documents being collected). Kept separate from `stage` above: once
    # registration completes this same thread_id becomes "authed", and
    # `stage` needs to still read as "new" at that point so authed_entry's
    # first-touch welcome fires correctly.
    onboarding_stage: Literal["awaiting_documents"]

    # Output fields — every terminal node sets ALL of these explicitly
    # (via _output() below) so a stale value from a previous turn never
    # leaks into a response it doesn't belong to.
    reply: str
    response_type: str
    options: Optional[list]
    properties: Optional[list]
    doc_type: Optional[str]
    sources: Optional[list]


def _output(message, reply, response_type, *, options=None, properties=None,
            doc_type=None, sources=None, **extra) -> dict:
    return {
        "reply": reply,
        "response_type": response_type,
        "options": options,
        "properties": properties,
        "doc_type": doc_type,
        "sources": sources,
        "chat_history": [
            {"role": "user", "content": message},
            {"role": "assistant", "content": reply},
        ],
        **extra,
    }


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


def _authed_entry_node(state: ChatState) -> dict:
    """Loads/refreshes the customer profile. On the very first authenticated
    turn of a session, also greets and asks the property question directly
    (terminal for this turn) — every later turn falls through to routing."""
    user_context = state["user_context"]
    profile = state.get("customer_profile")
    if not profile:
        profile = discover_account(user_context["user_id"], user_context["customer_id"])

    if state.get("stage", "new") == "new":
        card = get_property_choice_message()
        first_name = (user_context.get("full_name") or "there").split()[0]
        reply = f"Welcome back, {first_name}! {card['message']}"
        out = _output(state["message"], reply, "mcq", options=card["options"])
        out["customer_profile"] = profile
        out["stage"] = "awaiting_property_choice"
        out["just_handled"] = True
        return out

    return {"customer_profile": profile, "just_handled": False}


def _lap_node(state: ChatState) -> dict:
    reply = (
        "Perfect. To verify your property I'll need a few details from your "
        "Sale Deed — the registration number, the address, and the area in sq. ft. "
        "You can upload the document and I'll extract these, or type them in directly."
    )
    out = _output(state["message"], reply, "document_request", doc_type="sale_deed")
    out["stage"] = "lap_flow"
    return out


def _home_loan_node(state: ChatState) -> dict:
    reply = (
        "Would you like to choose a property from our verified pre-approved developer tie-ups "
        "in Kolkata, or do you have a different new property in mind?"
    )
    options = [
        {"id": "tie_ups", "label": "Our Tie-ups"},
        {"id": "own_choice", "label": "My Own Choice"},
    ]
    out = _output(state["message"], reply, "mcq", options=options)
    out["stage"] = "awaiting_tie_up_choice"
    return out


def _explain_choice_node(state: ChatState) -> dict:
    reply = (
        "Certainly! Here is an explanation of the two home loan paths we offer:\n\n"
        "1. **Loan Against Property (LAP)**: This option allows you to mortgage or leverage a property "
        "you ALREADY own (like your home, flat, or land) to secure a loan. You can use these funds for personal or business needs.\n\n"
        "2. **New Property Loan**: This is a standard home loan used to finance the purchase of a new property that you "
        "do not own yet. You can purchase a property from our pre-approved developer tie-ups in Kolkata (which are fast-tracked "
        "and skip extra inspections) or a new property of your own choice.\n\n"
        "Which of these paths would you like to proceed with?"
    )
    options = [
        {"id": "lap", "label": "I own a property (LAP)"},
        {"id": "home_loan", "label": "I want to buy a new property"},
    ]
    out = _output(state["message"], reply, "mcq", options=options)
    out["stage"] = "awaiting_property_choice"
    return out


def _show_inventory_node(state: ChatState) -> dict:
    inv = get_bank_inventory()
    reply = (
        f"Here are {inv['count']} premium developer tie-up properties available in Kolkata, "
        "all pre-approved and fast-tracked for financing. Please select one or ask me any questions about them:"
    )
    out = _output(state["message"], reply, "property_list", properties=inv["properties"])
    out["stage"] = "inventory_flow"
    out["shown_properties"] = inv["properties"]
    return out


def _own_choice_node(state: ChatState) -> dict:
    reply = (
        "Understood. You can choose to finance your own chosen new property. "
        "To get started, please share the property details with me (such as address and price) "
        "or upload any property documents you have on hand for our team to review."
    )
    out = _output(state["message"], reply, "text")
    out["stage"] = "general"
    return out


def _property_followup_node(state: ChatState) -> dict:
    message = state["message"]
    lower = message.lower().strip()
    session_id = state.get("session_id", "")

    # 1. Handle "continue with this"
    if "continue" in lower or "proceed" in lower:
        from session_store import mark_step
        mark_step(session_id, "property", "completed")
        mark_step(session_id, "risk", "active", set_active=True)
        out = _output(message, "Woho! Great choice!", "text")
        out["stage"] = "general"
        return out

    # 2. Handle database location question
    if "where" in lower and "database" in lower and ("property" in lower or "properties" in lower):
        reply = "The property database is located at `backend/mock_data/properties.json`."
        return _output(message, reply, "text")

    # Load all inventory properties
    inventory = _load_bank_inventory()

    # 3. Detect property selection in the user's message
    match = re.search(r'\b(binv\d{3})\b', lower)
    if match:
        selected_id = match.group(1).upper()
        if selected_id in inventory:
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
            out = _output(message, reply, "property_list", properties=other_props, options=options)
            out["selected_property_id"] = selected_id
            out["stage"] = "inventory_flow"
            return out

    # 4. Handle follow-up Q&A for selected property
    selected_id = state.get("selected_property_id")
    if selected_id and selected_id in inventory:
        prop = inventory[selected_id]
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
        return _output(message, answer, "text", options=options)

    # Fallback to general shown properties
    shown = state.get("shown_properties", [])
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

    return _output(
        message, answer,
        "property_list" if shown else "text",
        properties=shown if shown else None,
    )


def _faq_node(state: ChatState) -> dict:
    message = state["message"]
    lower = message.lower().strip()
    if "where" in lower and "database" in lower and ("property" in lower or "properties" in lower):
        reply = "The property database is located at `backend/mock_data/properties.json`."
        return _output(message, reply, "text")
    answer, scored_docs = faq_agent(message, state.get("chat_history", []))
    return _output(message, answer, "text", sources=scored_docs)


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


def _route_after_entry(state: ChatState) -> str:
    # First touch after login already produced the MCQ — terminal.
    if state.get("just_handled"):
        return "end"

    stage = state.get("stage", "general")
    message = state["message"]
    lower = message.lower().strip()

    # Intercept property ID or continue/proceed or where database is located anywhere
    if "continue" in lower or "proceed" in lower:
        return "property_followup"
    if "where" in lower and "database" in lower and ("property" in lower or "properties" in lower):
        return "property_followup"
    if re.search(r'\bbinv\d{3}\b', lower):
        return "property_followup"

    # 1. Explanation query during choice stage
    if stage == "awaiting_property_choice" and (
        "what are those" in lower or "explain" in lower or "what is" in lower or "difference" in lower
    ):
        return "explain_choice"

    # 2. Re-route choice transitions deterministically
    if stage == "awaiting_property_choice":
        if "lap" in lower or "own a property" in lower or "mortgage" in lower:
            return "lap"
        elif "new property" in lower or "buy" in lower or "home loan" in lower or "buy a property" in lower:
            return "home_loan"

    # 3. Transition from awaiting_tie_up_choice
    if stage == "awaiting_tie_up_choice":
        if "yes" in lower or "tie" in lower or "inventory" in lower or "connect" in lower or "new" in lower or "show" in lower:
            return "show_inventory"
        elif "no" in lower or "own" in lower:
            return "own_choice"

    label = _route_stage_label(message, stage)
    if label == "property_followup" and stage != "inventory_flow":
        label = "faq"  # nothing shown yet to follow up on
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
        "explain_choice": "explain_choice",
        "show_inventory": "show_inventory",
        "own_choice": "own_choice",
        "property_followup": "property_followup",
        "faq": "faq",
    },
)
_graph.add_edge("lap", END)
_graph.add_edge("home_loan", END)
_graph.add_edge("explain_choice", END)
_graph.add_edge("show_inventory", END)
_graph.add_edge("own_choice", END)
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
    }
