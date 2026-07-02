"""
database/appointments.py
===========================
Manual-review appointment booking, backed by Supabase (`appointments`
table). Purely additive — doesn't touch session_store.py or
chat_graph.py's in-memory state. Works for any customer.
"""

from database.supabase_client import supabase


def create_appointment(
    customer_id: str,
    customer_name: str,
    session_id: str,
    appointment_date: str,
    appointment_time: str,
    branch: str,
    reason: str,
    contact_phone: str = None,
) -> dict | None:
    try:
        row = {
            "customer_id": customer_id,
            "customer_name": customer_name,
            "session_id": session_id,
            "appointment_date": appointment_date,
            "appointment_time": appointment_time,
            "branch": branch,
            "reason": reason,
            "contact_phone": contact_phone,
            "status": "confirmed",
        }
        res = supabase.table("appointments").insert(row).execute()
        return res.data[0] if res.data else None
    except Exception:
        return None


def get_appointment(session_id: str) -> dict | None:
    try:
        res = (
            supabase.table("appointments")
            .select("*")
            .eq("session_id", session_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception:
        return None


def get_latest_appointment_by_customer(customer_id: str) -> dict | None:
    """Most recent CONFIRMED appointment for a customer, regardless of
    which session booked it. Cancelled appointments are filtered out by
    the status predicate, so callers can show the result directly."""
    try:
        res = (
            supabase.table("appointments")
            .select("*")
            .eq("customer_id", customer_id)
            .eq("status", "confirmed")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception as e:
        print(f"get_latest_appointment error: {e}")
        return None


def get_appointment_by_id(appointment_id: str) -> dict | None:
    """Looked up before cancelling — lets the caller verify the
    appointment actually belongs to whoever is requesting the
    cancellation before any mutation happens."""
    try:
        res = (
            supabase.table("appointments")
            .select("*")
            .eq("id", appointment_id)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception:
        return None


def cancel_appointment(appointment_id: str) -> dict | None:
    try:
        res = (
            supabase.table("appointments")
            .update({"status": "cancelled"})
            .eq("id", appointment_id)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception:
        return None
