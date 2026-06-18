"""
agents/kyc_agent.py
=====================
Runs ONLY for new customers (after OTP verification in auth_agent).

Step 1 — Identity KYC: Aadhaar + PAN → mock_kyc_api → verify identity.
         (mock_kyc_api can also opportunistically return financial_data,
         but the real financial_data used for registration now comes from
         agents/financial_document_agent.py, which extracts it from the
         salary slips / bank statements / ITR the customer uploads after
         this step — see main.py's /kyc/upload.)
Step 2 — Confirm & register: creates the bank_customers record in SQLite,
         issues JWT. This is the moment "new user" becomes a real customer.

Each document upload also marks progress in session_store so the
frontend's workflow panel reflects real backend state.
"""

import hashlib
from database.init_db import get_connection
from mock_api.mock_kyc_api import mock_kyc_api
from services.jwt_service import create_token
from session_store import mark_step, set_customer, set_credit
from mock_api.mock_cibil_api import mock_cibil_api


def verify_identity(
    session_id: str,
    temp_id: str,
    phone: str,
    aadhaar_number: str,
    pan_number: str,
    passport_number: str = None,
) -> dict:
    """
    Step 1: Verify identity documents.

    The frontend has already run OCR/extraction on the uploaded
    Aadhaar and PAN images — this receives the extracted numbers,
    not the raw files.

    Returns
    -------
    {
        success           : bool,
        verified_name     : str | None,
        verified_dob      : str | None,
        face_match_score  : float | None,
        documents_missing : list,
        financial_data    : dict | None,
        message           : str,
        next_step         : "financial_documents" | None
    }
    """
    mark_step(session_id, "kyc", "active", set_active=True)

    result = mock_kyc_api(
        aadhaar_number=aadhaar_number,
        pan_number=pan_number,
        passport_number=passport_number,
        include_financial_docs=True,
    )

    if not result["success"]:
        mark_step(session_id, "kyc", "failed")
        return {
            "success": False,
            "verified_name": None,
            "verified_dob": None,
            "face_match_score": None,
            "documents_missing": result.get("documents_missing", []),
            "financial_data": None,
            "message": result.get("failure_reason", "We couldn't verify those documents. Please check the numbers and try again."),
            "next_step": None,
        }

    return {
        "success": True,
        "temp_id": temp_id,
        "phone": phone,
        "aadhaar_number": aadhaar_number,
        "pan_number": pan_number,
        "verified_name": result["verified_name"],
        "verified_dob": result["verified_dob"],
        "verified_address": result["verified_address"],
        "face_match_score": result["face_match_score"],
        "pan_verified": result["pan_verified"],
        "aadhaar_verified": result["aadhaar_verified"],
        "documents_missing": result["documents_missing"],
        "financial_data": result.get("financial_data"),
        "message": f"All verified, {result['verified_name'].split()[0]}! KYC verification completed successfully.",
        "next_step": "financial_documents",
    }


def complete_registration(
    session_id: str,
    temp_id: str,
    phone: str,
    aadhaar_number: str,
    pan_number: str,
    verified_name: str,
    verified_dob: str,
    verified_address: str,
    financial_data: dict,
) -> dict:
    """
    Step 2: Create the bank_customers record + issue JWT.
    Marks kyc as completed and account as completed in session_store.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        user_id = f"USR{phone[-6:]}"
        customer_id = f"CUST{phone[-6:]}"
        temp_password_hash = hashlib.sha256(f"temp_{phone}".encode()).hexdigest()

        bank_statement = (financial_data or {}).get("bank_statement", {})
        salary_slips = (financial_data or {}).get("salary_slip", [])
        monthly_income = salary_slips[0].get("gross_salary") if salary_slips else None
        employer_name = salary_slips[0].get("employer") if salary_slips else None

        cursor.execute("""
            INSERT INTO users (user_id, password_hash, full_name, phone, role, is_active)
            VALUES (?, ?, ?, ?, 'customer', 1)
        """, (user_id, temp_password_hash, verified_name, phone))

        cursor.execute("""
            INSERT INTO bank_customers (
                customer_id, user_id, full_name, phone, date_of_birth, address,
                pan_number, aadhaar_number, kyc_status, kyc_completed_date,
                monthly_income, employment_type, employer_name,
                customer_segment, risk_flag, fraud_flag,
                bounced_cheques_12m, avg_monthly_balance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'verified', datetime('now'),
                      ?, 'salaried', ?, 'standard', 0, 0, 0, ?)
        """, (
            customer_id, user_id, verified_name, phone, verified_dob, verified_address,
            pan_number, aadhaar_number, monthly_income, employer_name,
            bank_statement.get("avg_monthly_balance", 0),
        ))

        cursor.execute("DELETE FROM pending_registrations WHERE temp_id = ?", (temp_id,))
        conn.commit()

        token = create_token(user_id=user_id, full_name=verified_name, customer_id=customer_id)

        mark_step(session_id, "kyc", "completed")
        mark_step(session_id, "account", "completed")
        set_customer(session_id, customer_id, verified_name, is_existing=False)

        # Retrieve and set credit score
        cibil = mock_cibil_api(pan_number)
        if cibil["success"]:
            score = cibil["cibil_score"]
            rating = "Excellent" if score >= 750 else "Good" if score >= 700 else "Fair" if score >= 600 else "Poor"
            set_credit(session_id, score, rating)

        return {
            "success": True,
            "jwt_token": token,
            "user_id": user_id,
            "customer_id": customer_id,
            "full_name": verified_name,
            "is_existing": False,
            "message": f"Welcome aboard, {verified_name.split()[0]}! Your account is all set up.",
            "next_step": "property_question",
        }

    except Exception as e:
        conn.rollback()
        mark_step(session_id, "kyc", "failed")
        return {
            "success": False,
            "jwt_token": None,
            "message": f"Registration failed: {str(e)}",
            "next_step": None,
        }
    finally:
        conn.close()
