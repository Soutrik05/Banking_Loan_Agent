"""
services/otp_service.py
========================
Generates and verifies OTPs.
Currently MOCK mode — prints OTP to console / shows on UI.
To switch to real SMS: plug in Twilio credentials in .env
"""

import random
import string
from datetime import datetime, timedelta, timezone
from database.init_db import get_connection

OTP_EXPIRY_MINUTES = 5


def generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def send_otp(user_id: str, phone: str, purpose: str = "login") -> dict:
    """
    Generates OTP, stores in DB, and 'sends' it.

    In MOCK mode: returns OTP in response (show on UI for demo).
    In PRODUCTION: integrate Twilio here and never return OTP.

    Returns:
        {"success": True, "otp": "123456", "message": "...", "mock": True}
    """
    otp_code = generate_otp()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)).isoformat()

    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Invalidate any previous unused OTPs for this user
        cursor.execute("""
            UPDATE otp_store SET is_used = 1
            WHERE user_id = ? AND purpose = ? AND is_used = 0
        """, (user_id, purpose))

        # Insert new OTP
        cursor.execute("""
            INSERT INTO otp_store (user_id, phone, otp_code, purpose, expires_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, phone, otp_code, purpose, expires_at))

        conn.commit()

        # ── MOCK MODE ──────────────────────────────────────────────────
        # In production, call Twilio here:
        # client = Client(TWILIO_SID, TWILIO_TOKEN)
        # client.messages.create(to=phone, from_=TWILIO_PHONE,
        #     body=f"Your OTP is {otp_code}. Valid for {OTP_EXPIRY_MINUTES} mins.")
        # ──────────────────────────────────────────────────────────────

        return {
            "success": True,
            "otp": otp_code,          # Remove this in production!
            "phone": phone,
            "expires_in_minutes": OTP_EXPIRY_MINUTES,
            "message": f"OTP sent to {phone[-4:].rjust(len(phone), '*')}",
            "mock": True,             # Flag to show OTP on UI in demo
        }

    except Exception as e:
        return {"success": False, "otp": None, "message": str(e), "mock": True}
    finally:
        conn.close()


def verify_otp(user_id: str, otp_entered: str, purpose: str = "login") -> dict:
    """
    Verifies OTP against DB.

    Returns:
        {"success": True/False, "message": str}
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT otp_code, expires_at, is_used
            FROM otp_store
            WHERE user_id = ? AND purpose = ? AND is_used = 0
            ORDER BY created_at DESC LIMIT 1
        """, (user_id, purpose))

        row = cursor.fetchone()

        if not row:
            return {"success": False, "message": "No active OTP found. Please request a new one."}

        if row["is_used"]:
            return {"success": False, "message": "OTP already used."}

        expires_at = datetime.fromisoformat(row["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            return {"success": False, "message": f"OTP expired. Please request a new one."}

        if otp_entered.strip() != row["otp_code"]:
            return {"success": False, "message": "Incorrect OTP. Please try again."}

        # Mark OTP as used
        cursor.execute("""
            UPDATE otp_store SET is_used = 1
            WHERE user_id = ? AND purpose = ? AND is_used = 0
        """, (user_id, purpose))
        conn.commit()

        return {"success": True, "message": "OTP verified successfully."}

    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()
