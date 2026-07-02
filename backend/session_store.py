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


# ---------------------------------------------------------------------------
# Per-customer approved EMI tracking
# Keyed by customer_id (not session_id) so it survives New Application.
# Cleared when the customer explicitly resets or logs out.
# ---------------------------------------------------------------------------

_CUSTOMER_APPROVED_EMI: dict[str, float] = {}


def set_customer_approved_emi(customer_id: str, emi: float) -> None:
    """Record the monthly EMI of a just-approved loan so the next
    credit assessment in this browser session can factor it in."""
    _CUSTOMER_APPROVED_EMI[customer_id] = emi


def get_customer_approved_emi(customer_id: str) -> float:
    """Return the in-session approved EMI for this customer, or 0."""
    return _CUSTOMER_APPROVED_EMI.get(customer_id, 0.0)


def clear_customer_approved_emi(customer_id: str) -> None:
    """Remove the stored approved EMI (e.g. on logout or manual reset)."""
    _CUSTOMER_APPROVED_EMI.pop(customer_id, None)
