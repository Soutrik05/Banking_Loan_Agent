"""
database/conversations.py
============================
Persistent conversation history backed by Supabase (`conversations` +
`messages` tables). Purely additive — the in-memory session_store.py /
chat_graph.py memory (which drives the actual chat behaviour) is untouched.
This module only powers the ChatGPT-style history sidebar.
"""

from datetime import datetime, timezone
from typing import Optional

from openai import AzureOpenAI

from database.supabase_client import supabase
from utils.config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_VERSION,
    CHAT_DEPLOYMENT,
)

_title_client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version=AZURE_OPENAI_API_VERSION,
)


def get_or_create_conversation(customer_id: str, session_id: str) -> dict:
    """Returns the conversation row for this session_id, creating one if needed."""
    existing = (
        supabase.table("conversations")
        .select("*")
        .eq("session_id", session_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        return existing.data[0]

    created = (
        supabase.table("conversations")
        .insert({
            "customer_id": customer_id,
            "session_id": session_id,
            "title": "New Application",
        })
        .execute()
    )
    return created.data[0]


def get_conversations(customer_id: str) -> list:
    """All conversations for a customer, most recently updated first."""
    res = (
        supabase.table("conversations")
        .select("*")
        .eq("customer_id", customer_id)
        .order("updated_at", desc=True)
        .execute()
    )
    return res.data or []


def get_conversation_messages(conversation_id: str) -> list:
    """All messages in a conversation, oldest first."""
    res = (
        supabase.table("messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=False)
        .execute()
    )
    return res.data or []


def save_message(
    conversation_id: str,
    role: str,
    content: str,
    message_type: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """Inserts a message row and bumps the parent conversation's updated_at."""
    row = {
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
    }
    if message_type is not None:
        row["message_type"] = message_type
    if metadata is not None:
        row["metadata"] = metadata

    res = supabase.table("messages").insert(row).execute()

    supabase.table("conversations").update(
        {"updated_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", conversation_id).execute()

    return res.data[0] if res.data else {}


def update_conversation_title(conversation_id: str, title: str):
    supabase.table("conversations").update({"title": title}).eq("id", conversation_id).execute()


def _decision_title(d: dict) -> str:
    """Build a concise conversation title from a loan decision card."""
    decision = d.get("decision", "")
    amount = d.get("loan_amount") or 0
    flow = d.get("flow_type", "loan")
    label = "LAP" if flow == "lap" else "Home Loan"
    if decision == "approved":
        return f"{label} Approved — Rs.{amount / 100000:.1f}L"
    elif decision == "rejected":
        return f"{label} Application — Declined"
    return f"{label} Application — Review Pending"


def save_loan_decision(session_id: str, decision_data: dict) -> None:
    """Persist the loan decision card to the conversation row so the
    sidebar can show a status badge and the title updates immediately
    to reflect the outcome — no LLM call required."""
    try:
        title = _decision_title(decision_data)
        supabase.table("conversations").update({
            "loan_decision": decision_data,
            "title": title,
        }).eq("session_id", session_id).execute()
    except Exception as e:
        print(f"save_loan_decision error: {e}")


def generate_conversation_title(messages: list, customer_name: str) -> str:
    """
    Short, descriptive sidebar title for any conversation — works for any
    customer, any loan topic. Called once a conversation has its first
    real exchange; on any failure, falls back to a generic per-customer
    title rather than breaking the chat response.
    """
    try:
        context = "\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')}"
            for m in messages[:4]
        )

        response = _title_client.chat.completions.create(
            model=CHAT_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Generate a SHORT 4-6 word title for this banking loan conversation. "
                        "Examples: 'LAP Application - Ballygunge', 'Home Loan Inquiry Salt Lake', "
                        "'Property Eligibility Check'. Return ONLY the title, nothing else."
                    ),
                },
                {"role": "user", "content": context},
            ],
            max_tokens=20,
        )
        title = (response.choices[0].message.content or "").strip().strip('"')
        return title or f"{customer_name}'s Loan Application"
    except Exception:
        return f"{customer_name}'s Loan Application"
