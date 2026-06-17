"""
agents/auth_agent.py
=====================
Handles authentication for BOTH user types.

Existing customer  → phone/user_id + password + OTP → JWT
New user           → phone number + OTP → proceed to KYC (no password)

Session lives in sessionStorage on frontend.
Tab closed = session gone = must login again.
"""

import hashlib
from database.init_db import get_connection
from services.otp_service import send_otp, verify_otp
from services.jwt_service import create_token


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# ─────────────────────────────────────────────────────────────
# EXISTING CUSTOMER FLOW
# Step 1 → Step 2 → Step 3
# ─────────────────────────────────────────────────────────────

def existing_verify_credentials(user_id: str, password: str) -> dict:
    """
    Step 1 (Existing): Verify user_id + password.
    On success → send OTP to registered phone.

    Returns
    -------
    {
        success    : bool,
        user_id    : str | None,
        full_name  : str | None,
        phone      : str | None,
        message    : str,
        next_step  : "otp" | None
    }
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, password_hash, full_name, phone, is_active
            FROM users WHERE user_id = ?
        """, (user_id.strip(),))
        user = cursor.fetchone()

        if not user:
            return {
                "success": False, "user_id": None,
                "full_name": None, "phone": None,
                "message": "User ID not found.",
                "next_step": None,
            }

        if not user["is_active"]:
            return {
                "success": False, "user_id": None,
                "full_name": None, "phone": None,
                "message": "Account deactivated. Please contact support.",
                "next_step": None,
            }

        if _hash_password(password) != user["password_hash"]:
            return {
                "success": False, "user_id": None,
                "full_name": None, "phone": None,
                "message": "Incorrect password. Please try again.",
                "next_step": None,
            }

        # Password correct → send OTP
        otp_result = send_otp(
            user_id=user["user_id"],
            phone=user["phone"],
            purpose="login",
        )

        return {
            "success": True,
            "user_id": user["user_id"],
            "full_name": user["full_name"],
            "phone": user["phone"],
            "otp": otp_result.get("otp"),        # shown on UI in demo mode
            "message": otp_result["message"],
            "next_step": "otp",
        }

    except Exception as e:
        return {
            "success": False, "user_id": None,
            "full_name": None, "phone": None,
            "message": str(e), "next_step": None,
        }
    finally:
        conn.close()


def existing_verify_otp(user_id: str, otp_entered: str) -> dict:
    """
    Step 2 (Existing): Verify OTP → issue JWT.

    Returns
    -------
    {
        success      : bool,
        jwt_token    : str | None,
        user_id      : str | None,
        full_name    : str | None,
        customer_id  : str | None,
        is_existing  : True,
        message      : str,
        next_step    : "account_discovery" | None
    }
    """
    otp_result = verify_otp(
        user_id=user_id,
        otp_entered=otp_entered,
        purpose="login",
    )
    if not otp_result["success"]:
        return {
            "success": False, "jwt_token": None,
            "user_id": None, "full_name": None,
            "customer_id": None, "is_existing": True,
            "message": otp_result["message"],
            "next_step": None,
        }

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.user_id, u.full_name, bc.customer_id
            FROM users u
            LEFT JOIN bank_customers bc ON u.user_id = bc.user_id
            WHERE u.user_id = ?
        """, (user_id,))
        row = cursor.fetchone()

        if not row:
            return {
                "success": False, "jwt_token": None,
                "user_id": None, "full_name": None,
                "customer_id": None, "is_existing": True,
                "message": "User not found.",
                "next_step": None,
            }

        customer_id = row["customer_id"] or user_id
        token = create_token(
            user_id=row["user_id"],
            full_name=row["full_name"],
            customer_id=customer_id,
        )

        return {
            "success": True,
            "jwt_token": token,
            "user_id": row["user_id"],
            "full_name": row["full_name"],
            "customer_id": customer_id,
            "is_existing": True,
            "message": f"Welcome back, {row['full_name']}! Login successful.",
            "next_step": "account_discovery",
        }

    except Exception as e:
        return {
            "success": False, "jwt_token": None,
            "user_id": None, "full_name": None,
            "customer_id": None, "is_existing": True,
            "message": str(e), "next_step": None,
        }
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# NEW USER FLOW
# Step 1 → Step 2
# ─────────────────────────────────────────────────────────────

def new_user_request_otp(phone: str) -> dict:
    """
    Step 1 (New user): Takes phone number → sends OTP.
    No password needed — they are not registered yet.

    Checks if this phone already exists in DB.
    If yes → tells them to use existing customer login.

    Returns
    -------
    {
        success          : bool,
        phone            : str,
        already_exists   : bool,
        otp              : str | None,   # demo mode only
        message          : str,
        next_step        : "otp" | "existing_login" | None
    }
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id FROM users WHERE phone = ?",
            (phone.strip(),)
        )
        existing = cursor.fetchone()

        if existing:
            return {
                "success": False,
                "phone": phone,
                "already_exists": True,
                "otp": None,
                "message": (
                    "This phone number is already registered with us. "
                    "Please use the existing customer login."
                ),
                "next_step": "existing_login",
            }

        # New phone — generate a temporary user_id and send OTP
        # We use phone as temp user_id for OTP storage
        temp_user_id = f"NEW_{phone.replace('+', '').replace('-', '')}"

        # Insert temp record so OTP table FK doesn't fail
        cursor.execute("""
            INSERT OR IGNORE INTO pending_registrations (temp_id, phone, created_at)
            VALUES (?, ?, datetime('now'))
        """, (temp_user_id, phone))
        conn.commit()

        otp_result = send_otp(
            user_id=temp_user_id,
            phone=phone,
            purpose="new_registration",
        )

        return {
            "success": True,
            "phone": phone,
            "already_exists": False,
            "temp_id": temp_user_id,
            "otp": otp_result.get("otp"),        # shown on UI in demo mode
            "message": otp_result["message"],
            "next_step": "otp",
        }

    except Exception as e:
        return {
            "success": False, "phone": phone,
            "already_exists": False, "otp": None,
            "message": str(e), "next_step": None,
        }
    finally:
        conn.close()


def new_user_verify_otp(temp_id: str, phone: str, otp_entered: str) -> dict:
    """
    Step 2 (New user): Verify OTP.
    On success → proceed to KYC. No JWT yet — they are not a user yet.
    JWT is issued AFTER KYC is complete and they are registered.

    Returns
    -------
    {
        success     : bool,
        phone       : str,
        temp_id     : str,
        is_existing : False,
        message     : str,
        next_step   : "kyc" | None
    }
    """
    otp_result = verify_otp(
        user_id=temp_id,
        otp_entered=otp_entered,
        purpose="new_registration",
    )

    if not otp_result["success"]:
        return {
            "success": False,
            "phone": phone,
            "temp_id": temp_id,
            "is_existing": False,
            "message": otp_result["message"],
            "next_step": None,
        }

    return {
        "success": True,
        "phone": phone,
        "temp_id": temp_id,
        "is_existing": False,
        "message": "Phone verified! Let's now verify your identity.",
        "next_step": "kyc",
    }
