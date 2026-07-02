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
    generate_conversation_title,
    save_loan_decision,
    get_loan_decision_by_customer,
)
from database.document_store import upload_property_document, get_property_documents
from database.appointments import (
    create_appointment,
    get_appointment,
    cancel_appointment,
    get_appointment_by_id,
    get_latest_appointment_by_customer,
)
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

class AppointmentRequest(BaseModel):
    customer_id: str
    session_id: str
    appointment_date: str
    appointment_time: str
    branch: str
    reason: str
    contact_phone: Optional[str] = None
    token: str

class CancelAppointmentRequest(BaseModel):
    appointment_id: str
    token: str

class AdvisorRequest(BaseModel):
    message: str
    session_id: str
    token: str
    conversation_history: list = []


def _get_user_from_token(token: str) -> dict:
    """Decode JWT and return payload, raises 401 if invalid.

    verify_token() always returns a (truthy) dict, even on failure —
    {"valid": False, "message": ...} — so the emptiness check alone never
    actually rejected a bad/expired token. Checking payload["valid"] is
    what makes every endpoint that wraps a token through here (chat, KYC
    uploads, appointments, sale-deed upload) actually enforce auth instead
    of silently passing an unusable payload through to a KeyError later.
    """
    payload = verify_token(token)
    if not payload or not payload.get("valid"):
        detail = (payload or {}).get("message", "Invalid or expired session")
        raise HTTPException(status_code=401, detail=detail)
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

    # Include the customer's real CIBIL score (mock_cibil_api, keyed by
    # their PAN) so the frontend credit-score card shows the correct value
    # from the moment they log in — not a hardcoded placeholder that only
    # corrects itself after a credit assessment runs.
    try:
        if discovery.get("pan_number"):
            cibil = mock_cibil_api(discovery["pan_number"])
            if cibil.get("success"):
                score = cibil["cibil_score"]
                rating = "Excellent" if score >= 750 else "Good" if score >= 700 else "Fair" if score >= 600 else "Poor"
                discovery["cibil_score"] = score
                discovery["cibil_rating"] = rating
    except Exception:
        pass

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
            save_message(conversation_id, "assistant", response["reply"], message_type=response.get("type"), metadata=response.get("metadata"))
            response["conversation_id"] = conversation_id

            # Auto-title the conversation right after its first real exchange
            # (1 user + 1 assistant message) so the sidebar stops showing the
            # generic "New Application" placeholder. Best-effort — must never
            # affect the chat response itself.
            all_messages = get_conversation_messages(conversation_id)
            if len(all_messages) == 2:
                import threading
                def _bg_title():
                    try:
                        title = generate_conversation_title(all_messages, user_context["full_name"])
                        update_conversation_title(conversation_id, title)
                    except Exception as e:
                        print(f"Title Gen Error: {e}")
                threading.Thread(target=_bg_title, daemon=True).start()
        except Exception as e:
            print(f"SUPABASE ERROR: {e}")

        # Persist loan decision to the conversation row so the sidebar
        # can show a status badge and an outcome-aware title without
        # waiting for the next LLM title-generation background task.
        if response.get("type") == "loan_decision" and response.get("display_card"):
            try:
                save_loan_decision(req.session_id, response["display_card"])
            except Exception as e:
                print(f"loan decision persist error: {e}")


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
def list_conversations(customer_id: str, token: str):
    """
    Returns only the authenticated caller's own conversations. The
    customer_id query param is accepted for URL-shape compatibility but is
    NEVER trusted — the token's own customer_id is always what's actually
    queried, so one customer can't pull another's chat history by passing
    a different customer_id (or a stolen/guessed one) in the query string.
    """
    user_context = _get_user_from_token(token)
    try:
        return get_conversations(user_context["customer_id"])
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


@app.get("/loan-decision/latest")
def get_latest_loan_decision(token: str):
    """
    Most recent loan decision for the authenticated customer, across ALL
    their conversations — survives session rotation and page reloads.
    """
    user_context = _get_user_from_token(token)
    decision = get_loan_decision_by_customer(user_context["customer_id"])
    return {"loan_decision": decision}


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
        docs = get_property_documents(session_id)
        # Defense in depth: session_id alone isn't cryptographically tied
        # to a customer, so only return rows whose own customer_id matches
        # the token holder's, even if the session_id were guessed/reused.
        return [d for d in docs if d.get("customer_id") == payload.get("customer_id")]
    except Exception:
        return []


# Maps each expected slot type to the OCR document_type values that are
# valid for it. Keeps the mapping explicit rather than a string-equals
# check, so a single slot can accept closely related types (e.g. "noc"
# and "noc_builder" are interchangeable from OCR's perspective).
_EXPECTED_DOC_CONTENT: dict[str, list[str]] = {
    "sale_deed":                ["sale_deed"],
    "succession_certificate":   ["succession_certificate"],
    "mutation_certificate":     ["mutation_certificate"],
    "gift_deed":                ["gift_deed"],
    "encumbrance_certificate":  ["encumbrance_certificate"],
    "noc_builder":              ["noc_builder", "noc"],
}

_DOC_DISPLAY_NAMES: dict[str, str] = {
    "sale_deed":               "Sale Deed",
    "succession_certificate":  "Succession/Will Certificate",
    "mutation_certificate":    "Mutation Certificate",
    "gift_deed":               "Gift Deed",
    "encumbrance_certificate": "Encumbrance Certificate",
    "noc_builder":             "NOC from Builder/Society",
    "noc":                     "NOC from Builder/Society",
}


@app.post("/property/upload-sale-deed")
async def property_upload_sale_deed(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    token: str = Form(...),
    customer_id: str = Form(...),
    doc_type: str = Form("sale_deed"),
):
    """
    AI-driven property-document intake for the LAP flow — handles Sale
    Deed, Succession Certificate, Mutation Certificate, and Gift Deed
    uploads alike (doc_type tells us which). Works for ANY customer's ANY
    valid document — OCR extracts the fields, nothing here is hardcoded
    to a specific person or scenario.

    Also validates that the OCR-detected document_type matches the slot's
    expected type, so a user can't accidentally (or deliberately) upload
    a Succession Certificate into the Mutation Certificate slot and have
    it accepted.
    """
    user_context = _get_user_from_token(token)

    file_bytes = await file.read()
    extraction = extract_sale_deed_fields(file_bytes, file.filename, customer_id)
    if not extraction["success"]:
        return {"success": False, "doc_type": doc_type, "message": extraction["message"]}

    # Document type validation — only checked when the OCR produced a
    # confident document_type detection AND the slot has a known expectation.
    extracted_fields = extraction["extracted_fields"]
    extracted_doc_type = extracted_fields.get("document_type")
    allowed_types = _EXPECTED_DOC_CONTENT.get(doc_type)

    if extracted_doc_type and allowed_types and extracted_doc_type not in allowed_types:
        expected_name = _DOC_DISPLAY_NAMES.get(doc_type, doc_type)
        found_name = _DOC_DISPLAY_NAMES.get(extracted_doc_type, extracted_doc_type)
        return {
            "success": False,
            "extracted_fields": {},
            "document_type_mismatch": True,
            "expected_type": doc_type,
            "found_type": extracted_doc_type,
            "message": (
                f"❌ Wrong document uploaded. This slot expects a "
                f"{expected_name} but you uploaded a {found_name}. "
                f"Please upload the correct document."
            ),
        }

    try:
        upload_property_document(
            session_id=session_id,
            customer_id=user_context["customer_id"],
            doc_type=doc_type,
            file_bytes=file_bytes,
            filename=file.filename,
        )
    except Exception:
        pass  # Supabase storage is best-effort here — extraction already succeeded

    return {
        "success": True,
        "extracted_fields": extracted_fields,
        "doc_type": doc_type,
        "message": extraction["message"],
        "next_step": "confirm_and_verify",
    }


# ─────────────────────────────────────────────────────────────
# APPOINTMENTS — manual-review property verification follow-up
# ─────────────────────────────────────────────────────────────

@app.post("/appointments/book")
def book_appointment(req: AppointmentRequest):
    """
    Books a property-verification appointment for ANY authenticated
    customer. Works the same regardless of who's logged in — every
    field comes from the request body, nothing hardcoded.
    """
    user_context = _get_user_from_token(req.token)
    try:
        # SECURITY: always book under the TOKEN's customer_id — never the
        # request body's. A stale/mismatched customer_id sent by the client
        # (e.g. state left over from a previous login on the same tab) was
        # how one customer's appointment could end up attached to another
        # customer's profile.
        appointment = create_appointment(
            customer_id=user_context["customer_id"],
            customer_name=user_context.get("full_name") or "Customer",
            session_id=req.session_id,
            appointment_date=req.appointment_date,
            appointment_time=req.appointment_time,
            branch=req.branch,
            reason=req.reason,
            contact_phone=req.contact_phone,
        )
        if not appointment:
            return {"success": False, "message": "Could not book the appointment. Please try again."}
        return {
            "success": True,
            "appointment_id": appointment.get("id"),
            "message": "Appointment confirmed!",
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/appointments/cancel")
def cancel_appointment_endpoint(req: CancelAppointmentRequest):
    """
    Cancels an existing appointment for ANY authenticated customer — but
    only if it actually belongs to them. The appointment is looked up by
    id and its customer_id cross-checked against the token's BEFORE any
    mutation, so one customer can never cancel another's appointment by
    guessing/reusing an appointment_id.
    """
    user_context = _get_user_from_token(req.token)
    try:
        existing = get_appointment_by_id(req.appointment_id)
        if not existing:
            return {"success": False, "message": "Appointment not found."}
        if existing.get("customer_id") != user_context["customer_id"]:
            return {"success": False, "message": "This appointment does not belong to you."}
        if existing.get("status") == "cancelled":
            return {"success": True, "message": "Appointment is already cancelled."}

        updated = cancel_appointment(req.appointment_id)
        if not updated:
            return {"success": False, "message": "Could not cancel the appointment. Please try again."}
        return {"success": True, "message": "Appointment cancelled successfully."}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.get("/appointments/latest")
def get_latest_appointment(token: str):
    """
    Most recent CONFIRMED appointment for the authenticated customer,
    regardless of which session booked it — so the context panel keeps
    showing the appointment after a New Application / page reload rotates
    the session_id. Cancelled appointments are never returned.

    NOTE: must stay registered BEFORE /appointments/{session_id} below,
    otherwise "latest" would be captured as a session_id.
    """
    user_context = _get_user_from_token(token)
    try:
        appt = get_latest_appointment_by_customer(user_context["customer_id"])
        return {"appointment": appt}
    except Exception:
        return {"appointment": None}


@app.get("/appointments/{session_id}")
def fetch_appointment(session_id: str, token: str):
    user_context = _get_user_from_token(token)
    try:
        appointment = get_appointment(session_id)
        # session_id is a client-generated UUID, not cryptographically tied
        # to a customer — confirm the appointment actually belongs to the
        # token holder before returning it, so a reused/guessed session_id
        # can never leak another customer's appointment.
        if appointment and appointment.get("customer_id") != user_context["customer_id"]:
            return {"appointment": None}
        return {"appointment": appointment}
    except Exception:
        return {"appointment": None}


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


# ─────────────────────────────────────────────────────────────
# FINANCIAL ADVISOR — personal financial Q&A with customer context
# ─────────────────────────────────────────────────────────────

@app.post("/advisor/chat")
async def advisor_chat(req: AdvisorRequest):
    """
    Financial advisor endpoint — handles any financial query with full
    customer context. Separate from the main loan-application chat;
    accessible any time the customer is authenticated.
    """
    user_context = _get_user_from_token(req.token)

    # Surface the most recent loan decision from the session if available
    session = get_session(req.session_id) or {}
    loan_decision = session.get("loan_decision")

    from agents.financial_advisor_agent import get_financial_advice

    reply = get_financial_advice(
        customer_id=user_context["customer_id"],
        user_message=req.message,
        conversation_history=req.conversation_history,
        loan_decision=loan_decision,
    )

    return {"reply": reply, "type": "advisor"}
