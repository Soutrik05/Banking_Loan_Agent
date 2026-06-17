"""
backend/session_store.py
===========================
Minimal in-memory store tracking each session's real progress
through the loan workflow. Keyed by session_id.

This is what powers the right-hand workflow panel and credit score
on the frontend — replacing the hardcoded appState.ts constants.

NOT a database. Dies on server restart. Fine for demo; swap for
Redis or a DB table when this goes to production.
"""

from typing import Optional, Literal
from datetime import datetime

WorkflowStepId = Literal[
    "auth", "account", "kyc", "property", "risk", "credit", "decision"
]

_SESSIONS: dict[str, dict] = {}


def _default_session() -> dict:
    return {
        "customer_id": None,
        "full_name": None,
        "is_existing": None,
        "steps": {
            "auth":     "pending",
            "account":  "pending",
            "kyc":      "pending",
            "property": "pending",
            "risk":     "pending",
            "credit":   "pending",
            "decision": "pending",
        },
        "active_step": None,        # which step is currently "active" (spinner)
        "credit_score": None,       # set once credit_agent runs
        "credit_rating": None,
        "loan_decision": None,
        "updated_at": datetime.utcnow().isoformat(),
    }


def get_session(session_id: str) -> dict:
    if session_id not in _SESSIONS:
        _SESSIONS[session_id] = _default_session()
    return _SESSIONS[session_id]


def mark_step(session_id: str, step: WorkflowStepId, status: str, set_active: bool = False):
    """
    status: 'pending' | 'active' | 'completed' | 'failed'
    """
    session = get_session(session_id)
    session["steps"][step] = status
    if set_active:
        session["active_step"] = step
    session["updated_at"] = datetime.utcnow().isoformat()
    return session


def set_customer(session_id: str, customer_id: str, full_name: str, is_existing: bool):
    session = get_session(session_id)
    session["customer_id"] = customer_id
    session["full_name"] = full_name
    session["is_existing"] = is_existing
    return session


def set_credit(session_id: str, score: int, rating: str):
    session = get_session(session_id)
    session["credit_score"] = score
    session["credit_rating"] = rating
    return session


def set_decision(session_id: str, decision: dict):
    session = get_session(session_id)
    session["loan_decision"] = decision
    return session


def reset_session(session_id: str):
    _SESSIONS[session_id] = _default_session()
    return _SESSIONS[session_id]
