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

from database.supabase_client import supabase


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
