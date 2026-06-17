"""
services/jwt_service.py
========================
Handles JWT token creation, verification, and session management.
Uses HS256 algorithm with a secret key from .env
"""

import uuid
import json
import base64
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from database.init_db import get_connection

# ── In production load from .env ──────────────────────────────────────────
import os
JWT_SECRET = os.getenv("JWT_SECRET", "banking_agent_super_secret_key_change_in_prod")
JWT_EXPIRY_HOURS = 24


# ── Minimal JWT implementation (no extra library needed) ──────────────────

def _b64encode(data: dict | str) -> str:
    if isinstance(data, dict):
        data = json.dumps(data, separators=(",", ":"))
    return base64.urlsafe_b64encode(data.encode()).rstrip(b"=").decode()


def _b64decode(data: str) -> dict:
    padding = 4 - len(data) % 4
    data += "=" * padding
    return json.loads(base64.urlsafe_b64decode(data).decode())


def _sign(header_b64: str, payload_b64: str) -> str:
    msg = f"{header_b64}.{payload_b64}"
    sig = hmac.new(JWT_SECRET.encode(), msg.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).rstrip(b"=").decode()


def create_token(user_id: str, full_name: str, customer_id: str) -> str:
    """Creates a JWT token and stores session in DB."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=JWT_EXPIRY_HOURS)

    header = _b64encode({"alg": "HS256", "typ": "JWT"})
    payload = _b64encode({
        "sub": user_id,
        "name": full_name,
        "cid": customer_id,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    })
    signature = _sign(header, payload)
    token = f"{header}.{payload}.{signature}"

    # Store session in DB
    session_id = str(uuid.uuid4())
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO sessions (session_id, user_id, jwt_token, expires_at)
            VALUES (?, ?, ?, ?)
        """, (session_id, user_id, token, expires_at.isoformat()))
        conn.commit()
    finally:
        conn.close()

    return token


def verify_token(token: str) -> dict:
    """
    Verifies a JWT token.

    Returns:
        {"valid": True, "user_id": ..., "full_name": ..., "customer_id": ...}
        or
        {"valid": False, "message": "..."}
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {"valid": False, "message": "Invalid token format."}

        header_b64, payload_b64, signature = parts

        # Verify signature
        expected_sig = _sign(header_b64, payload_b64)
        if not hmac.compare_digest(signature, expected_sig):
            return {"valid": False, "message": "Token signature invalid."}

        # Decode payload
        payload = _b64decode(payload_b64)

        # Check expiry
        if datetime.fromtimestamp(payload["exp"], tz=timezone.utc) < datetime.now(timezone.utc):
            return {"valid": False, "message": "Token expired. Please login again."}

        # Update last_used_at in DB
        conn = get_connection()
        try:
            conn.execute("""
                UPDATE sessions SET last_used_at = datetime('now')
                WHERE jwt_token = ? AND is_active = 1
            """, (token,))
            conn.commit()
        finally:
            conn.close()

        return {
            "valid": True,
            "user_id": payload["sub"],
            "full_name": payload["name"],
            "customer_id": payload["cid"],
        }

    except Exception as e:
        return {"valid": False, "message": str(e)}


def invalidate_token(token: str):
    """Logs out — marks session as inactive."""
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE sessions SET is_active = 0
            WHERE jwt_token = ?
        """, (token,))
        conn.commit()
    finally:
        conn.close()
