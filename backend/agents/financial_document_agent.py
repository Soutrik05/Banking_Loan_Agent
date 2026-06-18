"""
agents/financial_document_agent.py
=====================================
Runs after KYC identity verification succeeds (kyc_agent.verify_identity)
and before kyc_agent.complete_registration(). Asks the new customer to
upload income-proof documents, extracts structured fields from the PDFs
with pdfplumber (text extraction only -- no OCR, so scanned/image-only
PDFs won't parse), and assembles everything into the financial_data dict
that complete_registration() already expects.

Required documents:
  - Last 3 Salary Slips            (salary_slip)
  - Last 6 Months Bank Statements  (bank_statement)
  - Latest ITR                     (itr, optional)

Storage here uses the same "in-memory, dies on restart, fine for demo"
pattern as session_store.py -- swap for a real table/object store before
production.
"""

import io
import re
from typing import Optional

import pdfplumber

# ---------------------------------------------------------------------------
# Document checklist
# ---------------------------------------------------------------------------

DOCUMENT_REQUIREMENTS = [
    {"doc_type": "salary_slip", "label": "Last 3 Salary Slips", "required": True, "max_files": 3},
    {"doc_type": "bank_statement", "label": "Last 6 Months Bank Statements", "required": True, "max_files": 6},
    {"doc_type": "itr", "label": "Latest ITR", "required": False, "max_files": 1},
]

_VALID_DOC_TYPES = {d["doc_type"] for d in DOCUMENT_REQUIREMENTS}

# ---------------------------------------------------------------------------
# In-memory state
# ---------------------------------------------------------------------------

# temp_id -> identity fields stashed right after verify_identity succeeds,
# so complete_registration can be called later without the frontend having
# to resend everything.
_PENDING_APPLICANTS: dict[str, dict] = {}

# session_id -> temp_id, so the chat graph (which only ever sees session_id,
# not temp_id) can look up upload progress for a session that hasn't been
# issued a JWT yet.
_SESSION_TO_TEMP: dict[str, str] = {}

# temp_id -> { doc_type: [ {filename, fields}, ... ] }
_UPLOADED_DOCS: dict[str, dict] = {}


def register_pending_applicant(
    session_id: str,
    temp_id: str,
    phone: str,
    aadhaar_number: str,
    pan_number: str,
    verified_name: str,
    verified_dob: str,
    verified_address: str,
) -> None:
    """Called once, right after KYC identity verification succeeds."""
    _PENDING_APPLICANTS[temp_id] = {
        "session_id": session_id,
        "temp_id": temp_id,
        "phone": phone,
        "aadhaar_number": aadhaar_number,
        "pan_number": pan_number,
        "verified_name": verified_name,
        "verified_dob": verified_dob,
        "verified_address": verified_address,
    }
    _SESSION_TO_TEMP[session_id] = temp_id
    _UPLOADED_DOCS.setdefault(temp_id, {})


def get_pending_applicant(temp_id: str) -> Optional[dict]:
    return _PENDING_APPLICANTS.get(temp_id)


def get_temp_id_for_session(session_id: str) -> Optional[str]:
    return _SESSION_TO_TEMP.get(session_id)


def is_awaiting_documents(session_id: str) -> bool:
    """True once identity has been verified for this session but
    registration hasn't completed yet. Used by the chat graph to route
    sessions that don't have a JWT yet into the kyc/financial_document
    nodes instead of treating them as an anonymous guest."""
    return get_temp_id_for_session(session_id) is not None


def clear_applicant(temp_id: str) -> None:
    """Called once registration completes -- frees the scratch data."""
    applicant = _PENDING_APPLICANTS.pop(temp_id, None)
    _UPLOADED_DOCS.pop(temp_id, None)
    if applicant:
        _SESSION_TO_TEMP.pop(applicant["session_id"], None)


# ---------------------------------------------------------------------------
# The ask
# ---------------------------------------------------------------------------

def get_financial_document_request() -> dict:
    """The message + checklist shown right after KYC succeeds (and again
    if the customer asks what's still needed)."""
    lines = [
        f"- {d['label']}" + ("" if d["required"] else " (optional)")
        for d in DOCUMENT_REQUIREMENTS
    ]
    message = (
        "Thanks, your identity is verified! To finish setting up your account, "
        "please upload the following:\n" + "\n".join(lines)
    )
    return {
        "message": message,
        "type": "document_request",
        "doc_type": "financial_documents",
        "documents_required": DOCUMENT_REQUIREMENTS,
    }


def get_upload_status(temp_id: str) -> dict:
    docs = _UPLOADED_DOCS.get(temp_id, {})
    uploaded = {doc_type: len(files) for doc_type, files in docs.items()}
    missing = [
        d["label"] for d in DOCUMENT_REQUIREMENTS
        if d["required"] and uploaded.get(d["doc_type"], 0) == 0
    ]
    return {"uploaded": uploaded, "missing": missing, "ready": len(missing) == 0}


# ---------------------------------------------------------------------------
# PDF extraction (pdfplumber, text-based -- not OCR)
# ---------------------------------------------------------------------------

def _extract_text(file_bytes: bytes) -> str:
    parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


def _search(pattern: str, text: str) -> Optional[str]:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _search_amount(pattern: str, text: str) -> Optional[float]:
    raw = _search(pattern, text)
    if not raw:
        return None
    cleaned = re.sub(r"[^\d.]", "", raw)
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _parse_salary_slip(text: str) -> dict:
    return {
        "employee_name": _search(r"(?:Employee Name|Emp(?:loyee)? Name|Name of Employee)\s*[:\-]\s*([A-Za-z .]+)", text),
        "employer": _search(r"(?:Employer|Company Name|Organi[sz]ation)\s*[:\-]\s*([A-Za-z0-9 .,&]+)", text),
        "designation": _search(r"(?:Designation|Job Title)\s*[:\-]\s*([A-Za-z .]+)", text),
        "pay_period": _search(r"(?:Pay Period|Payslip for the Month of|For the Month of|Salary Month|Month)\s*[:\-]?\s*([A-Za-z0-9 ,/\-]+)", text),
        "gross_salary": _search_amount(r"(?:Gross Salary|Gross Pay|Gross Earnings|Total Earnings)\s*[:\-]?\s*(?:Rs\.?|₹|INR)?\s*([\d,]+(?:\.\d+)?)", text),
        "net_salary": _search_amount(r"(?:Net Salary|Net Pay|Take Home(?: Pay)?|Net Amount)\s*[:\-]?\s*(?:Rs\.?|₹|INR)?\s*([\d,]+(?:\.\d+)?)", text),
        "pan": _search(r"PAN\s*(?:No\.?|Number)?\s*[:\-]?\s*([A-Z]{5}[0-9]{4}[A-Z])", text),
    }


def _parse_bank_statement(text: str) -> dict:
    return {
        "account_holder_name": _search(r"(?:Account Holder Name|Customer Name|Name)\s*[:\-]\s*([A-Za-z .]+)", text),
        "bank_name": _search(r"\b([A-Za-z .&]+?\s+Bank(?:\s+Ltd\.?|\s+Limited)?)\b", text),
        "account_number": _search(r"(?:A/C(?:\s*No)?\.?|Account\s*Number)\s*[:\-]?\s*([0-9Xx*]{4,20})", text),
        "statement_period": _search(r"(?:Statement Period|Period)\s*[:\-]\s*([A-Za-z0-9 ,/\-]+)", text),
        "avg_monthly_balance": _search_amount(r"(?:Average (?:Monthly )?Balance|Avg\.? (?:Monthly )?Balance)\s*[:\-]?\s*(?:Rs\.?|₹|INR)?\s*([\d,]+(?:\.\d+)?)", text),
        "closing_balance": _search_amount(r"(?:Closing Balance|Ending Balance)\s*[:\-]?\s*(?:Rs\.?|₹|INR)?\s*([\d,]+(?:\.\d+)?)", text),
    }


def _parse_itr(text: str) -> dict:
    return {
        "assessee_name": _search(r"(?:Name of Assessee|Assessee Name|Name)\s*[:\-]\s*([A-Za-z .]+)", text),
        "pan": _search(r"PAN\s*[:\-]?\s*([A-Z]{5}[0-9]{4}[A-Z])", text),
        "assessment_year": _search(r"Assessment Year\s*[:\-]?\s*([0-9]{4}-[0-9]{2,4})", text),
        "gross_total_income": _search_amount(r"(?:Gross Total Income|Total Income)\s*[:\-]?\s*(?:Rs\.?|₹|INR)?\s*([\d,]+(?:\.\d+)?)", text),
        "tax_paid": _search_amount(r"(?:Total Tax Paid|Tax Paid)\s*[:\-]?\s*(?:Rs\.?|₹|INR)?\s*([\d,]+(?:\.\d+)?)", text),
    }


_PARSERS = {
    "salary_slip": _parse_salary_slip,
    "bank_statement": _parse_bank_statement,
    "itr": _parse_itr,
}


def extract_financial_document(file_bytes: bytes, filename: str, doc_type: str) -> dict:
    """
    Extracts text from a digital PDF with pdfplumber and pulls out the
    structured fields relevant to doc_type. This is text extraction only,
    NOT OCR -- a scanned/image-only PDF will come back with little or no
    text and extraction will fail gracefully.
    """
    if doc_type not in _VALID_DOC_TYPES:
        return {"success": False, "message": f"Unknown document type '{doc_type}'.", "extracted_fields": {}}

    try:
        text = _extract_text(file_bytes)
    except Exception as e:
        return {"success": False, "message": f"Couldn't read '{filename}' as a PDF: {e}", "extracted_fields": {}}

    if len(text.strip()) < 20:
        return {
            "success": False,
            "message": (
                f"'{filename}' doesn't seem to contain readable text -- this looks like a "
                "scanned image PDF, which we can't process yet. Please upload a digital PDF."
            ),
            "extracted_fields": {},
        }

    fields = _PARSERS[doc_type](text)
    fields_found = [k for k, v in fields.items() if v]

    return {
        "success": True,
        "doc_type": doc_type,
        "filename": filename,
        "extracted_fields": fields,
        "fields_found": fields_found,
        "message": f"Got it — extracted {len(fields_found)} field(s) from {filename}.",
    }


def record_upload(temp_id: str, doc_type: str, extracted_fields: dict, filename: str) -> dict:
    """Stores one successfully-parsed document against this applicant and
    returns the updated overall upload status."""
    docs = _UPLOADED_DOCS.setdefault(temp_id, {})
    docs.setdefault(doc_type, []).append({"filename": filename, "fields": extracted_fields})
    return get_upload_status(temp_id)


def build_financial_data_payload(temp_id: str) -> dict:
    """Shapes everything uploaded so far into the financial_data dict that
    kyc_agent.complete_registration() already expects:
        {"bank_statement": {...}, "salary_slip": [...], "itr": {...} | None}
    """
    docs = _UPLOADED_DOCS.get(temp_id, {})

    salary_slips = [d["fields"] for d in docs.get("salary_slip", [])]

    bank_entries = [d["fields"] for d in docs.get("bank_statement", [])]
    bank_statement = {}
    if bank_entries:
        balances = [b["avg_monthly_balance"] for b in bank_entries if b.get("avg_monthly_balance")]
        bank_statement = {
            **bank_entries[-1],
            "avg_monthly_balance": (sum(balances) / len(balances)) if balances else bank_entries[-1].get("avg_monthly_balance"),
        }

    itr_entries = [d["fields"] for d in docs.get("itr", [])]

    return {
        "salary_slip": salary_slips,
        "bank_statement": bank_statement,
        "itr": itr_entries[-1] if itr_entries else None,
    }
