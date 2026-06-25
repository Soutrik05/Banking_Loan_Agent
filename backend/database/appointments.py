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
