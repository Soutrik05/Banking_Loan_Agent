"""
mock_apis/mock_cibil_api.py
Reads: credit_scores.json → ["credit_records"][pan]["cibil"]
Owner agent: credit_assessment_agent
"""
from __future__ import annotations
import datetime
from typing import Optional
from dataclasses import dataclass, asdict
from ._data_loader import load_json

def _now(): return datetime.datetime.utcnow().isoformat() + "Z"

@dataclass
class CIBILResponse:
    success: bool
    pan_number: str
    cibil_score: Optional[int]
    credit_rank: Optional[str]
    total_accounts: Optional[int]
    active_accounts: Optional[int]
    overdue_accounts: Optional[int]
    default_history: Optional[bool]
    days_past_due: Optional[int]
    payment_history_months: Optional[int]
    credit_utilisation_pct: Optional[float]
    recent_enquiries_6m: Optional[int]
    written_off_accounts: Optional[int]
    failure_reason: Optional[str]
    timestamp: str
    def to_dict(self): return asdict(self)

def mock_cibil_api(pan_number: str) -> dict:
    """
    Fetch CIBIL credit score for a PAN number.

    Reads from: credit_scores.json → ["credit_records"][pan]["cibil"]

    Parameters
    ----------
    pan_number : 10-character PAN e.g. "ABCRD1234F"

    Returns
    -------
    CIBILResponse as dict.
    cibil_score < 650 → eligibility agent applies rejection / fast-track rules
    success=False     → no bureau record found, treat as new credit user

    Fix over original
    -----------------
    Path was data["cibil"].get(pan) — wrong.
    Correct path: data["credit_records"][pan]["cibil"]
    """
    data = load_json("credit_scores.json")

    # correct nested path: credit_records → pan → cibil
    pan_record = data.get("credit_records", {}).get(pan_number)
    if not pan_record:
        return CIBILResponse(
            success=False, pan_number=pan_number,
            cibil_score=None, credit_rank=None,
            total_accounts=None, active_accounts=None,
            overdue_accounts=None, default_history=None,
            days_past_due=None, payment_history_months=None,
            credit_utilisation_pct=None, recent_enquiries_6m=None,
            written_off_accounts=None,
            failure_reason="No CIBIL record found for this PAN",
            timestamp=_now(),
        ).to_dict()

    record = pan_record.get("cibil", {})
    return CIBILResponse(
        success=True, pan_number=pan_number,
        cibil_score=record.get("score"),
        credit_rank=record.get("credit_rank"),
        total_accounts=record.get("total_accounts"),
        active_accounts=record.get("active_accounts"),
        overdue_accounts=record.get("overdue_accounts"),
        default_history=record.get("default_history"),
        days_past_due=record.get("days_past_due"),
        payment_history_months=record.get("payment_history_months"),
        credit_utilisation_pct=record.get("credit_utilisation_pct"),
        recent_enquiries_6m=record.get("recent_enquiries_6m"),
        written_off_accounts=record.get("written_off_accounts"),
        failure_reason=None,
        timestamp=_now(),
    ).to_dict()
