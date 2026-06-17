"""
mock_apis/mock_kyc_api.py
Reads: customers.json → ["kyc_documents"], ["financial_documents"]
Owner agent: kyc_agent
"""
from __future__ import annotations
import datetime, hashlib
from typing import Optional
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from ._data_loader import load_json
import datetime, hashlib, re

def _now(): return datetime.datetime.utcnow().isoformat() + "Z"

def _name_match(a: str, b: str) -> bool:
    """Fuzzy match — handles middle names and minor spelling variations."""
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio() >= 0.80

def _deterministic_face_score(aadhaar: str) -> float:
    """Same Aadhaar always gives same face score — no random()."""
    seed = int(hashlib.md5(aadhaar.encode()).hexdigest(), 16)
    return round(0.85 + (seed % 15) / 100, 2)   # 0.85 – 0.99

@dataclass
class KYCResponse:
    success: bool
    kyc_status: str             # "verified" | "failed" | "partial"
    verified_name: Optional[str]
    verified_dob: Optional[str]
    verified_address: Optional[str]
    pan_verified: bool
    aadhaar_verified: bool
    face_match_score: Optional[float]
    documents_submitted: list
    documents_missing: list
    financial_data: Optional[dict]
    failure_reason: Optional[str]
    timestamp: str
    def to_dict(self): return asdict(self)

def mock_kyc_api(
    aadhaar_number: Optional[str] = None,
    pan_number: Optional[str] = None,
    passport_number: Optional[str] = None,
    include_financial_docs: bool = True,
) -> dict:
    """
    Verify identity documents for new customers.

    Reads from: customers.json → ["kyc_documents"], ["financial_documents"]

    Parameters
    ----------
    aadhaar_number        : masked e.g. "XXXX-XXXX-1111"
    pan_number            : e.g. "ABCRD1234F"
    passport_number       : optional third factor
    include_financial_docs: also return salary slip / ITR data

    Returns
    -------
    KYCResponse as dict.
    kyc_status="verified" → proceed to property / loan pipeline
    kyc_status="failed"   → route to escalation_agent

    Fixes over original
    -------------------
    - face_match_score is deterministic (hashlib seed), not random()
    - name cross-match uses fuzzy 80% threshold not exact string ==
    - financial_data reads from ["financial_documents"][pan] correctly
    """
    data = load_json("customers.json")
    kyc_docs = data["kyc_documents"]
    fin_docs  = data["financial_documents"]

    submitted, missing = [], []

    if not aadhaar_number and not pan_number:
        return KYCResponse(False, "failed", None, None, None, False, False,
                           None, [], ["aadhaar","pan"], None,
                           "No identity documents provided", _now()).to_dict()

    # ── Aadhaar ──────────────────────────────────────────────────────────────
    aadhaar_data = None
    if aadhaar_number:
        submitted.append("aadhaar")
        aadhaar_data = kyc_docs["aadhaar"].get(aadhaar_number)

        if not aadhaar_data:

            aadhaar_valid = bool(
                re.match(r"^(\d{12}|XXXX-XXXX-\d{4})$", aadhaar_number)
            )

            if not aadhaar_valid:
                return KYCResponse(
                    False,
                    "failed",
                    None,
                    None,
                    None,
                    False,
                    False,
                    None,
                    submitted,
                    ["pan"] if not pan_number else [],
                    None,
                    "Invalid Aadhaar format",
                    _now()
                ).to_dict()

            aadhaar_data = {
                "name": "New Customer",
                "dob": "1995-01-01",
                "address": "Address Verified via Aadhaar Registry",
                "verified": True
            }

    else:
        missing.append("aadhaar")
        missing.append("aadhaar")

       # ── PAN ──────────────────────────────────────────────────────────────────
    pan_data = None
    if pan_number:
        submitted.append("pan")
        pan_data = kyc_docs["pan"].get(pan_number)

        if not pan_data:

            pan_valid = bool(
                re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]$", pan_number)
            )

            if not pan_valid:
                return KYCResponse(
                    False,
                    "failed",
                    None,
                    None,
                    None,
                    False,
                    bool(aadhaar_data),
                    None,
                    submitted,
                    missing,
                    None,
                    "Invalid PAN format",
                    _now()
                ).to_dict()

            pan_data = {
                "name": aadhaar_data["name"],
                "dob": aadhaar_data["dob"],
                "verified": True
            }

    else:
        missing.append("pan")

    # ── Cross-document name match (fuzzy) ────────────────────────────────────
    # ── Cross-document name match (fuzzy) ─────────────────────────
    if (
        aadhaar_data
        and pan_data
        and aadhaar_data["name"] != "New Customer"
    ):
        if not _name_match(aadhaar_data["name"], pan_data["name"]):
            return KYCResponse(
                False,
                "failed",
                None,
                None,
                None,
                True,
                True,
                None,
                submitted,
                missing,
                None,
                f"Name mismatch: Aadhaar='{aadhaar_data['name']}' "
                f"vs PAN='{pan_data['name']}'",
                _now()
            ).to_dict()

    # ── Face match score (deterministic) ─────────────────────────────────────
    face_score = None
    if aadhaar_number:
        stored = kyc_docs.get("face_match_scores", {}).get(aadhaar_number)
        face_score = stored if stored is not None else _deterministic_face_score(aadhaar_number)

    # ── Financial documents ───────────────────────────────────────────────────
    fin_data = None
    if include_financial_docs and pan_number:
        fin_data = fin_docs.get(pan_number)
        if fin_data:
            submitted.extend([k for k in ["salary_slip","bank_statement","itr"]
                               if fin_data.get(k) is not None])

    primary = aadhaar_data or pan_data
    return KYCResponse(
        success=True, kyc_status="verified",
        verified_name=primary["name"],
        verified_dob=primary.get("dob"),
        verified_address=aadhaar_data.get("address") if aadhaar_data else None,
        pan_verified=pan_data is not None,
        aadhaar_verified=aadhaar_data is not None,
        face_match_score=face_score,
        documents_submitted=submitted,
        documents_missing=missing,
        financial_data=fin_data,
        failure_reason=None,
        timestamp=_now(),
    ).to_dict()
