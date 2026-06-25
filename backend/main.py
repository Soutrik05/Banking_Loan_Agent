"""
backend_api/main.py
=====================
FastAPI bridge between the React frontend and the Python agents.

This is the ONLY new backend file needed. It imports your existing
agents directly — no rewriting of agent logic.

Run with:
    uvicorn backend_api.main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
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
from agents.financial_document_agent import (
    get_financial_document_request,
    register_pending_applicant,
    get_pending_applicant,
    extract_financial_document,
    record_upload,
    get_upload_status,
    build_financial_data_payload,
    clear_applicant,
)
from agents.property_agent import submit_own_property, get_bank_inventory, select_bank_property
from services.jwt_service import verify_token
from session_store import get_session, mark_step, set_customer, reset_session, set_credit
from mock_api.mock_cibil_api import mock_cibil_api
from database.init_db import get_connection
from database.conversations import (
    get_or_create_conversation,
    get_conversations,
    get_conversation_messages,
    save_message,
    update_conversation_title,
)
from database.document_store import upload_property_document, get_property_documents
from services.ocr_service import extract_sale_deed_fields

app = FastAPI(title="National Bank Loan Assistant API")

# Allow the React dev server to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

class UpdateConversationTitleRequest(BaseModel):
    title: str


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

    # Query and set credit score in session store
    if discovery.get("pan_number"):
        cibil = mock_cibil_api(discovery["pan_number"])
        if cibil["success"]:
            score = cibil["cibil_score"]
            rating = "Excellent" if score >= 750 else "Good" if score >= 700 else "Fair" if score >= 600 else "Poor"
            set_credit(req.session_id, score, rating)

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
    Routes every chat message through graph.chat_graph.run_chat_graph(),
    which keeps real conversation memory per session_id and uses an LLM
    router instead of brittle keyword matching. orchestrator_agent's
    classify_intent() is still used inside the graph for guest-intent
    classification.

    Login is enforced on the frontend, so token will be present once an
    existing customer reaches this screen. A brand-new customer who has
    completed KYC identity verification but not yet finished uploading
    financial documents won't have a token yet either -- the graph itself
    figures that out from session_id via session_store.
    """
    from graph.chat_graph import run_chat_graph

    user_context = None
    if req.token:
        user_context = _get_user_from_token(req.token)

    response = run_chat_graph(
        message=req.message,
        session_id=req.session_id,
        user_context=user_context,
    )

    # Persist to Supabase for the conversation-history sidebar. Best-effort —
    # a Supabase outage must never break the chat itself.
    if user_context is not None:
        try:
            conversation = get_or_create_conversation(user_context["customer_id"], req.session_id)
            conversation_id = conversation["id"]
            save_message(conversation_id, "user", req.message)
            save_message(conversation_id, "assistant", response["reply"], message_type=response.get("type"))
            response["conversation_id"] = conversation_id
        except Exception as e:
            print(f"SUPABASE ERROR: {e}")
    

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

    # Identity is verified but the account isn't created yet -- stash what
    # we'll need to finish registration once the financial documents are
    # uploaded, and hand back the document checklist so the frontend can
    # show it straight away.
    register_pending_applicant(
        session_id=req.session_id,
        temp_id=result["temp_id"],
        phone=result["phone"],
        aadhaar_number=result["aadhaar_number"],
        pan_number=result["pan_number"],
        verified_name=result["verified_name"],
        verified_dob=result["verified_dob"],
        verified_address=result["verified_address"],
    )
    doc_request = get_financial_document_request()

    return {
        **result,
        "message": f"{result['message']} {doc_request['message']}",
        "documents_required": doc_request["documents_required"],
    }


@app.post("/kyc/upload")
async def kyc_upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    temp_id: str = Form(...),
):
    """
    Uploads ONE financial document (salary slip / bank statement / ITR),
    extracts structured fields from it with pdfplumber, and records it
    against this applicant. Once every required document type has at
    least one upload, registration is completed automatically and a JWT
    is issued in the same response -- no separate confirmation step.
    """
    applicant = get_pending_applicant(temp_id)
    if not applicant:
        raise HTTPException(status_code=400, detail="No pending KYC session found for this temp_id. Please complete identity verification first.")

    file_bytes = await file.read()
    extraction = extract_financial_document(file_bytes, file.filename, doc_type)
    if not extraction["success"]:
        return {
        "success": False,
        "message": extraction["message"],
        "doc_type": doc_type,
        "status": get_upload_status(temp_id),
        "registration": None,
        "url": None,
    }

    status = record_upload(temp_id, doc_type, extraction["extracted_fields"], file.filename)

    registration = None
    if status["ready"]:
        financial_data = build_financial_data_payload(temp_id)
        reg_result = complete_registration(
            session_id=applicant["session_id"],
            temp_id=applicant["temp_id"],
            phone=applicant["phone"],
            aadhaar_number=applicant["aadhaar_number"],
            pan_number=applicant["pan_number"],
            verified_name=applicant["verified_name"],
            verified_dob=applicant["verified_dob"],
            verified_address=applicant["verified_address"],
            financial_data=financial_data,
        )
        if reg_result["success"]:
            registration = reg_result
            clear_applicant(temp_id)  # after capturing `status` above -- nothing below reads the store again
        else:
            registration = reg_result  # surfaces the failure message; applicant stays pending so they can retry

    return {
        "success": True,
        "message": extraction["message"],
        "doc_type": doc_type,
        "filename": file.filename,
        "extracted_fields": extraction["extracted_fields"],
        "fields_found": extraction["fields_found"],
        "status": status,
        "registration": registration,
        "url": f"uploaded://{file.filename}",
    }


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
        financial_data=req.financial_data or build_financial_data_payload(req.temp_id),
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    clear_applicant(req.temp_id)
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
    session = get_session(session_id)
    # If credit score is not yet set, but we have customer_id, try to fetch and set it
    if session.get("customer_id") and session.get("credit_score") is None:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT pan_number FROM bank_customers WHERE customer_id = ?", (session["customer_id"],))
            row = cursor.fetchone()
            if row and row["pan_number"]:
                cibil = mock_cibil_api(row["pan_number"])
                if cibil["success"]:
                    score = cibil["cibil_score"]
                    rating = "Excellent" if score >= 750 else "Good" if score >= 700 else "Fair" if score >= 600 else "Poor"
                    set_credit(session_id, score, rating)
        except Exception:
            pass
        finally:
            conn.close()
    return session


@app.post("/session/reset")
def session_reset(session_id: str):
    return reset_session(session_id)


# ─────────────────────────────────────────────────────────────
# CONVERSATIONS — persistent chat history sidebar (Supabase)
# ─────────────────────────────────────────────────────────────

@app.get("/conversations")
def list_conversations(customer_id: str):
    try:
        return get_conversations(customer_id)
    except Exception:
        return []


@app.get("/conversations/{conversation_id}/messages")
def list_conversation_messages(conversation_id: str):
    try:
        return get_conversation_messages(conversation_id)
    except Exception:
        return []


@app.patch("/conversations/{conversation_id}/title")
def rename_conversation(conversation_id: str, req: UpdateConversationTitleRequest):
    try:
        update_conversation_title(conversation_id, req.title)
        return {"success": True}
    except Exception as e:
        return {"success": False, "message": str(e)}


# ─────────────────────────────────────────────────────────────
# PROPERTY DOCUMENTS — Supabase Storage uploads
# ─────────────────────────────────────────────────────────────

@app.post("/property/upload-document")
async def property_upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    session_id: str = Form(...),
    token: str = Form(...),
):
    payload = verify_token(token)
    if not payload.get("valid"):
        raise HTTPException(status_code=401, detail=payload.get("message", "Invalid or expired session"))

    file_bytes = await file.read()
    try:
        return upload_property_document(
            session_id=session_id,
            customer_id=payload["customer_id"],
            doc_type=doc_type,
            file_bytes=file_bytes,
            filename=file.filename,
        )
    except Exception as e:
        return {"success": False, "file_path": None, "doc_type": doc_type, "message": str(e)}


@app.get("/property/documents")
def property_documents(session_id: str, token: str):
    payload = verify_token(token)
    if not payload.get("valid"):
        raise HTTPException(status_code=401, detail=payload.get("message", "Invalid or expired session"))
    try:
        return get_property_documents(session_id)
    except Exception:
        return []


@app.post("/property/upload-sale-deed")
async def property_upload_sale_deed(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    token: str = Form(...),
    customer_id: str = Form(...),
):
    """
    AI-driven Sale Deed intake for the LAP flow. Works for ANY customer's
    ANY valid Sale Deed — OCR extracts the fields, nothing here is
    hardcoded to a specific person or scenario.
    """
    user_context = _get_user_from_token(token)

    file_bytes = await file.read()
    extraction = extract_sale_deed_fields(file_bytes, file.filename, customer_id)
    if not extraction["success"]:
        return {"success": False, "message": extraction["message"]}

    try:
        upload_property_document(
            session_id=session_id,
            customer_id=user_context["customer_id"],
            doc_type="sale_deed",
            file_bytes=file_bytes,
            filename=file.filename,
        )
    except Exception:
        pass  # Supabase storage is best-effort here — extraction already succeeded

    return {
        "success": True,
        "extracted_fields": extraction["extracted_fields"],
        "message": extraction["message"],
        "next_step": "confirm_and_verify",
    }


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
