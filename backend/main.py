"""
backend_api/main.py
=====================
FastAPI bridge between the React frontend and the Python agents.

This is the ONLY new backend file needed. It imports your existing
agents directly — no rewriting of agent logic.

Run with:
    uvicorn backend_api.main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

# Your existing agents — imported directly, untouched
from agents.auth_agent import (
    existing_verify_credentials,
    existing_verify_otp,
    new_user_request_otp,
    new_user_verify_otp,
)
from agents.account_discovery_agent import discover_account, get_property_question
from agents.kyc_agent import verify_identity, complete_registration
from agents.property_agent import submit_own_property, get_bank_inventory, select_bank_property
from services.jwt_service import verify_token
from session_store import get_session, mark_step, set_customer, reset_session

app = FastAPI(title="National Bank Loan Assistant API")

# Allow the React dev server to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────
# Request/Response models
# ─────────────────────────────────────────────────────────────

class ExistingLoginRequest(BaseModel):
    session_id: str
    user_id: str
    password: str

class OTPVerifyRequest(BaseModel):
    session_id: str
    user_id: str
    otp: str

class NewUserOTPRequest(BaseModel):
    session_id: str
    phone: str

class NewUserOTPVerifyRequest(BaseModel):
    session_id: str
    temp_id: str
    phone: str
    otp: str

class ChatRequest(BaseModel):
    message: str
    session_id: str
    token: Optional[str] = None

class VerifyIdentityRequest(BaseModel):
    session_id: str
    temp_id: str
    phone: str
    aadhaar_number: str
    pan_number: str
    passport_number: Optional[str] = None

class CompleteRegistrationRequest(BaseModel):
    session_id: str
    temp_id: str
    phone: str
    aadhaar_number: str
    pan_number: str
    verified_name: str
    verified_dob: str
    verified_address: str
    financial_data: Optional[dict] = None

class SubmitPropertyRequest(BaseModel):
    session_id: str
    registration_number: str
    owner_name: str
    owner_pan: str
    address: str
    pincode: str
    area_sqft: int
    property_type: str = "residential_apartment"

class SelectInventoryRequest(BaseModel):
    session_id: str
    property_id: str


def _get_user_from_token(token: str) -> dict:
    """Decode JWT and return payload, raises 401 if invalid."""
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return payload


# ─────────────────────────────────────────────────────────────
# AUTH — Existing customer (password + OTP)
# ─────────────────────────────────────────────────────────────

@app.post("/auth/existing/login")
def existing_login(req: ExistingLoginRequest):
    """
    Step 1: Existing customer enters user_id + password.
    On success → OTP is sent, frontend shows OTP input.
    """
    mark_step(req.session_id, "auth", "active", set_active=True)
    result = existing_verify_credentials(req.user_id, req.password)
    if not result["success"]:
        mark_step(req.session_id, "auth", "failed")
        raise HTTPException(status_code=401, detail=result["message"])
    return result


@app.post("/auth/existing/verify-otp")
def existing_otp_verify(req: OTPVerifyRequest):
    """
    Step 2: Existing customer enters OTP.
    On success → JWT token issued, account discovery runs automatically.
    """
    result = existing_verify_otp(req.user_id, req.otp)
    if not result["success"]:
        mark_step(req.session_id, "auth", "failed")
        raise HTTPException(status_code=401, detail=result["message"])

    mark_step(req.session_id, "auth", "completed")

    # Immediately run account discovery so frontend gets everything in one call
    discovery = discover_account(result["user_id"], result["customer_id"])
    property_question = get_property_question(result["full_name"])

    mark_step(req.session_id, "account", "completed")
    set_customer(req.session_id, result["customer_id"], result["full_name"], is_existing=True)

    return {
        **result,
        "profile": discovery,
        "next_message": property_question,
    }


# ─────────────────────────────────────────────────────────────
# AUTH — New user (phone + OTP only, no password)
# ─────────────────────────────────────────────────────────────

@app.post("/auth/new/request-otp")
def new_user_otp_request(req: NewUserOTPRequest):
    """
    Step 1: New user enters phone number.
    If phone already registered → tells frontend to show existing login instead.
    """
    result = new_user_request_otp(req.phone)
    if not result["success"] and not result["already_exists"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@app.post("/auth/new/verify-otp")
def new_user_otp_verify(req: NewUserOTPVerifyRequest):
    """
    Step 2: New user enters OTP.
    On success → frontend routes to KYC upload screen. No JWT yet.
    """
    result = new_user_verify_otp(req.temp_id, req.phone, req.otp)
    if not result["success"]:
        raise HTTPException(status_code=401, detail=result["message"])
    mark_step(req.session_id, "auth", "completed")
    return result


# ─────────────────────────────────────────────────────────────
# SESSION — validate token on app reload
# ─────────────────────────────────────────────────────────────

@app.get("/auth/session")
def check_session(token: str):
    """
    Called when the app loads to check if sessionStorage token is still valid.
    """
    payload = _get_user_from_token(token)
    discovery = discover_account(payload["user_id"], payload["customer_id"])
    return {"valid": True, "profile": discovery}


# ─────────────────────────────────────────────────────────────
# CHAT — routes to orchestrator_agent
# ─────────────────────────────────────────────────────────────

@app.post("/chat")
def chat(req: ChatRequest):
    """
    Routes every chat message through orchestrator_agent.handle_message().
    Login is enforced on the frontend, so token should always be present
    once the user reaches this screen.
    """
    from agents.orchestrator_agent import handle_message

    user_context = None
    if req.token:
        user_context = _get_user_from_token(req.token)

    response = handle_message(
        message=req.message,
        session_id=req.session_id,
        user_context=user_context,
    )
    return response


# ─────────────────────────────────────────────────────────────
# KYC — new customer identity + financial verification
# ─────────────────────────────────────────────────────────────

@app.post("/kyc/verify-identity")
def kyc_verify_identity(req: VerifyIdentityRequest):
    result = verify_identity(
        session_id=req.session_id,
        temp_id=req.temp_id,
        phone=req.phone,
        aadhaar_number=req.aadhaar_number,
        pan_number=req.pan_number,
        passport_number=req.passport_number,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@app.post("/kyc/complete-registration")
def kyc_complete_registration(req: CompleteRegistrationRequest):
    result = complete_registration(
        session_id=req.session_id,
        temp_id=req.temp_id,
        phone=req.phone,
        aadhaar_number=req.aadhaar_number,
        pan_number=req.pan_number,
        verified_name=req.verified_name,
        verified_dob=req.verified_dob,
        verified_address=req.verified_address,
        financial_data=req.financial_data,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


# ─────────────────────────────────────────────────────────────
# PROPERTY — LAP (own property) vs Home Loan (bank inventory)
# ─────────────────────────────────────────────────────────────

@app.get("/property/inventory")
def property_inventory(city: Optional[str] = None, max_price: Optional[int] = None):
    return get_bank_inventory(city=city, max_price=max_price)


@app.post("/property/select-inventory")
def property_select_inventory(req: SelectInventoryRequest):
    result = select_bank_property(req.session_id, req.property_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@app.post("/property/submit-own")
def property_submit_own(req: SubmitPropertyRequest):
    result = submit_own_property(
        session_id=req.session_id,
        registration_number=req.registration_number,
        owner_name=req.owner_name,
        owner_pan=req.owner_pan,
        address=req.address,
        pincode=req.pincode,
        area_sqft=req.area_sqft,
        property_type=req.property_type,
    )
    return result


# ─────────────────────────────────────────────────────────────
# SESSION STATUS — powers the right-hand workflow panel + credit score
# ─────────────────────────────────────────────────────────────

@app.get("/session/status")
def session_status(session_id: str):
    """
    Polled by the frontend to render the real workflow panel.
    Replaces the hardcoded appState.ts workflowSteps + creditScore.
    """
    return get_session(session_id)


@app.post("/session/reset")
def session_reset(session_id: str):
    return reset_session(session_id)


# ─────────────────────────────────────────────────────────────
# PUBLIC — interest rates, no auth required
# ─────────────────────────────────────────────────────────────

@app.get("/rates")
def get_rates():
    import json
    with open("mock_data/policy_rules.json") as f:
        policy = json.load(f)
    return policy["interest_rate_bands"]


@app.get("/health")
def health():
    return {"status": "ok"}
