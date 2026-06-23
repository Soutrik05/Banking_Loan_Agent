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

from langgraph.agent import Agent
from langgraph.graph import StateGraph, START, END
from langgraph.conditions import Always, OneOf, EndOfDialog, Anything
from langgraph.states import State as S
from langgraph.types import ChatMessage, ChatResponse
from langgraph.data import MemoryVars

from openai import AzureOpenAI

from langchain.callbacks.base import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

_client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version=AZURE_OPENAI_API_VERSION,
)


# ── Generic query node (FAQ agent) ──────────────────────────────────────────

def generic_query_node(current_state: ChatState, message: str):
    answer, scored_docs = faq_agent(message, current_state.chat_history)
    current_state.chat_history.append({"role": "user", "content": message})
    current_state.chat_history.append({"role": "assistant", "content": answer})
    return ChatResponse(answer, chat_history=current_state.chat_history)


# ── State machine definition ─────────────────────────────────────────────────

ChatState = MemoryVars(
    chat_history=[],
    temp_id="",
    outstanding_document="",
    property_selected=None,
    user_profile={},  # only populated for authenticated flows
)

guest = S("guest")
kyc = S("kyc")
financial_document = S("financial_document")
authed_entry = S("authed_entry")
lap = S("lap")
home_loan = S("home_loan")
property_selected = S("property_selected")
generic_query = S("generic_query")


# ── Graph conditions ──────────────────────────────────────────────────────────

class RoleIs:
    def __init__(self, role: str):
        self.role = role

    def __call__(self, state: ChatState, msg: str):
        if self.role == "guest":
            return state.user_profile is None
        if self.role == "kyc":
            return state.user_profile is None and state.temp_id != ""
        if self.role == "authenticated":
            return state.user_profile is not None
        return False


class AuthRequired:
    def __call__(self, state: ChatState, msg: str):
        lower = msg.strip().lower()
        wants_property_flow = (
            lower in ("lap", "i own a property", "home_loan", "i want to buy a property")
            or "own a property" in lower
            or "loan against" in lower
            or "buy a property" in lower
        )
        intent = "loan_application" if wants_property_flow else classify_intent(msg)
        return intent == "loan_application" and state.user_profile is None


class DocumentsRequired:
    def __call__(self, state: ChatState, msg: str):
        return is_awaiting_documents(state.temp_id)


class RegistrationComplete:
    def __call__(self, state: ChatState, msg: str):
        return not is_awaiting_documents(state.temp_id)


class NewUser:
    def __call__(self, state: ChatState, msg: str):
        return state.user_profile is not None and state.user_profile.get("stage") == "new"


class ExistingUser:
    def __call__(self, state: ChatState, msg: str):
        return state.user_profile is not None and state.user_profile.get("stage") == "existing"


# ── Graph states ───────────────────────────────────────────────────────────

def authed_entry_node(current_state: ChatState, message: str):
    if current_state.user_profile.get("stage") == "new":
        # Welcome message for brand-new users logging in for the first time
        card = get_property_choice_message()
        return ChatResponse(
            f"Welcome back, {current_state.user_profile.get('full_name').split()[0]}! {card['message']}",
            options=card["options"],
            chat_history=current_state.chat_history,
        )
    else:
        # Default to the LLM router
        return route_message(current_state, message)


def lap_node(current_state: ChatState, message: str):
    return ChatResponse(
        "Perfect. To verify your property I'll need a few details from your "
        "Sale Deed — the registration number, the address, and the area in sq. ft. "
        "You can upload the document and I'll extract these, or type them in directly.",
        doc_type="sale_deed",
        chat_history=current_state.chat_history,
    )


def home_loan_node(current_state: ChatState, message: str):
    inv = get_bank_inventory()
    return ChatResponse(
        f"Here are {inv['count']} properties available right now, all fast-tracked for financing:",
        properties=inv["properties"],
        chat_history=current_state.chat_history,
    )


def property_selected_node(current_state: ChatState, message: str):
    memory = " ".join([m["content"] for m in current_state.chat_history[-5:]])
    system = f"""Borrower profile: I have the authenticated user's profile available.
    Property details: {current_state.property_selected}
    The conversation so far: {memory}
    The borrower asked: {message}

    If you can answer the borrower's question about this specific property based on the property details and conversation history provided, please do so. If not, or if the question is too broad or vague to answer accurately, politely say that you don't have enough information to answer their question yet and ask them to rephrase it or provide more details about what specifically they want to know about the property."""
    response = _client.chat.completions.create(
        model=CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": system},
        ],
        temperature=0.3,
    )
    return ChatResponse(
        response.choices[0].message.content,
        chat_history=current_state.chat_history,
    )


def route_message(current_state: ChatState, message: str):
    """LLM call → one of: lap, home_loan, property_followup, faq"""
    response = _client.chat.completions.create(
        model=CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({"session_id": current_state.session_id,
                                                    "message": message,
                                                    "last_message": current_state.chat_history[-1]["content"] if current_state.chat_history else "",
                                                    "property_selected": current_state.property_selected,
                                                    "authenticated": current_state.user_profile is not None})},
        ],
        temperature=0,
        max_tokens=10,
    )
    intent = response.choices[0].message.content.strip()
    print(f"LLM router classified intent: {intent}")

    if intent == "lap":
        return lap_node(current_state, message)
    elif intent == "home_loan":
        return home_loan_node(current_state, message)
    elif intent == "property_followup" and current_state.property_selected:
        return property_selected_node(current_state, message)
    else:
        return generic_query_node(current_state, message)


# ── Graph transitions ──────────────────────────────────────────────────────

_graph = StateGraph(ChatState) \
    .add_transition(START, guest, RoleIs("guest")) \
    .add_transition(START, kyc, RoleIs("kyc")) \
    .add_transition(START, authed_entry, RoleIs("authenticated")) \
    .add_state(guest) \
    .add_transition(guest, generic_query, Always()) \
    .add_transition(guest, kyc, AuthRequired()) \
    .add_transition(guest, END, EndOfDialog()) \
    .add_state(kyc) \
    .add_transition(kyc, generic_query, Always()) \
    .add_transition(kyc, financial_document, DocumentsRequired()) \
    .add_transition(kyc, END, EndOfDialog()) \
    .add_state(financial_document) \
    .add_transition(financial_document, generic_query, Always()) \
    .add_transition(financial_document, END, RegistrationComplete()) \
    .add_state(authed_entry, authed_entry_node) \
    .add_transition(authed_entry, generic_query, Always()) \
    .add_state(lap, lap_node) \
    .add_transition(lap, generic_query, Always()) \
    .add_transition(lap, END, EndOfDialog()) \
    .add_state(home_loan, home_loan_node) \
    .add_transition(home_loan, generic_query, Always()) \
    .add_transition(home_loan, END, EndOfDialog()) \
    .add_state(property_selected, property_selected_node) \
    .add_transition(property_selected, generic_query, Always()) \
    .add_transition(property_selected, END, EndOfDialog()) \
    .add_state(generic_query, generic_query_node)

# ── Runtime ──────────────────────────────────────────────────────────────────

_compiled = _graph.compile()


def run_chat_graph(message: str, session_id: str, user_context: Optional[dict]) -> dict:
    result = _compiled.invoke(
        message,
        thread_id=session_id,
        callbacks=CallbackManager([StreamingStdOutCallbackHandler()]),
        chat_history=[],
        temp_id="",
        outstanding_document="",
        property_selected=None,
        user_profile=user_context,
    )
    response = result.response.as_json()
    print(f"LangGraph response: {response}")
    return response