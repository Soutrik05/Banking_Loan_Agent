"""
mock_apis/mock_auth_api.py
Reads: customers.json → ["users"]
Owner agent: auth_agent

Simple username + password authentication.
On success issues a signed JWT token (24hr expiry).
No OTP, no MFA, no session store needed.
"""
from __future__ import annotations

import datetime
import hashlib
import os
from typing import Optional
from dataclasses import dataclass, asdict

import jwt

from ._data_loader import load_json

JWT_SECRET    = os.getenv("JWT_SECRET", "national-bank-demo-secret-key-2025")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def _issue_token(user_id: str, role: str) -> str:
    payload = {
        "user_id": user_id,
        "role":    role,
        "exp":     datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXPIRY_HOURS),
        "iat":     datetime.datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


@dataclass
class AuthResponse:
    success: bool
    user_id: Optional[str]
    full_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    role: Optional[str]
    jwt_token: Optional[str]
    auth_method: str                # "password" | "jwt"
    failure_reason: Optional[str]
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)


def mock_auth_api(
    user_id:   Optional[str] = None,
    password:  Optional[str] = None,
    jwt_token: Optional[str] = None,
) -> dict:
    """
    Authenticate a user via username+password or validate an existing JWT.

    Flow 1 — Login
    --------------
    mock_auth_api(user_id="USR001", password="Pass@1234")
    → success=True, jwt_token=<signed JWT>

    Flow 2 — Token validation (subsequent requests)
    ------------------------------------------------
    mock_auth_api(jwt_token=<token>)
    → success=True, user_id and role extracted from token

    Reads from
    ----------
    customers.json → ["users"]

    Parameters
    ----------
    user_id   : bank user ID e.g. "USR001"
    password  : plain-text password
    jwt_token : previously issued JWT for validation

    Returns
    -------
    AuthResponse as dict.
    Orchestrator checks success=True before proceeding.
    """
    data  = load_json("customers.json")
    users = data["users"]

    # ── Flow 2: JWT token validation ─────────────────────────────────────────
    if jwt_token:
        payload = _decode_token(jwt_token)
        if not payload:
            return AuthResponse(
                success=False, user_id=None, full_name=None,
                email=None, phone=None, role=None,
                jwt_token=None, auth_method="jwt",
                failure_reason="Invalid or expired JWT token",
                timestamp=_now(),
            ).to_dict()

        uid  = payload["user_id"]
        user = users.get(uid, {})
        return AuthResponse(
            success=True,
            user_id=uid,
            full_name=user.get("full_name"),
            email=user.get("email"),
            phone=user.get("phone"),
            role=payload.get("role", "customer"),
            jwt_token=jwt_token,
            auth_method="jwt",
            failure_reason=None,
            timestamp=_now(),
        ).to_dict()

    # ── Flow 1: Username + password login ────────────────────────────────────
    if not user_id or not password:
        return AuthResponse(
            success=False, user_id=None, full_name=None,
            email=None, phone=None, role=None,
            jwt_token=None, auth_method="password",
            failure_reason="user_id and password are required",
            timestamp=_now(),
        ).to_dict()

    user = users.get(user_id)

    if not user:
        return AuthResponse(
            success=False, user_id=None, full_name=None,
            email=None, phone=None, role=None,
            jwt_token=None, auth_method="password",
            failure_reason="User not found",
            timestamp=_now(),
        ).to_dict()

    if not user["is_active"]:
        return AuthResponse(
            success=False, user_id=None, full_name=None,
            email=None, phone=None, role=None,
            jwt_token=None, auth_method="password",
            failure_reason="Account suspended — contact bank support",
            timestamp=_now(),
        ).to_dict()

    if hashlib.sha256(password.encode()).hexdigest() != user["password_hash"]:
        return AuthResponse(
            success=False, user_id=None, full_name=None,
            email=None, phone=None, role=None,
            jwt_token=None, auth_method="password",
            failure_reason="Incorrect password",
            timestamp=_now(),
        ).to_dict()

    token = _issue_token(user_id, user.get("role", "customer"))
    return AuthResponse(
        success=True,
        user_id=user_id,
        full_name=user["full_name"],
        email=user["email"],
        phone=user["phone"],
        role=user["role"],
        jwt_token=token,
        auth_method="password",
        failure_reason=None,
        timestamp=_now(),
    ).to_dict()
