"""
mock_apis/mock_customer_lookup.py
Reads: customers.json → ["bank_customers"]
Owner agent: account_discovery_agent
"""
from __future__ import annotations
import datetime
from typing import Optional
from dataclasses import dataclass, asdict
from ._data_loader import load_json

def _now(): return datetime.datetime.utcnow().isoformat() + "Z"

@dataclass
class CustomerLookupResponse:
    found: bool
    customer_id: Optional[str]
    user_id: str
    full_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    date_of_birth: Optional[str]
    address: Optional[str]
    pan_number: Optional[str]
    aadhaar_number: Optional[str]
    kyc_status: Optional[str]
    kyc_completed_date: Optional[str]
    account_numbers: list
    account_open_date: Optional[str]
    monthly_income: Optional[float]
    employment_type: Optional[str]
    employer_name: Optional[str]
    existing_loans: list
    documents_on_file: list
    customer_segment: Optional[str]
    relationship_manager: Optional[str]
    risk_flag: Optional[bool]
    fraud_flag: Optional[bool]
    bounced_cheques_12m: Optional[int]
    avg_monthly_balance: Optional[float]
    failure_reason: Optional[str]
    timestamp: str
    def to_dict(self): return asdict(self)

def mock_customer_lookup(user_id: str) -> dict:
    """
    Check if an authenticated user is an existing bank customer.

    Reads from: customers.json → ["bank_customers"]

    Parameters
    ----------
    user_id : Auth user ID returned by mock_auth_api e.g. "USR001"

    Returns
    -------
    CustomerLookupResponse as dict.
    found=True  → existing customer, load profile, skip KYC
    found=False → new customer, route to kyc_agent

    Note: bank_customers is keyed by user_id (not customer_id).
    Users not in this section are new customers — not an error.
    """
    data = load_json("customers.json")
    # bank_customers keyed by user_id directly
    record = data["bank_customers"].get(user_id)

    if not record:
        return CustomerLookupResponse(
            found=False, customer_id=None, user_id=user_id,
            full_name=None, email=None, phone=None,
            date_of_birth=None, address=None,
            pan_number=None, aadhaar_number=None,
            kyc_status=None, kyc_completed_date=None,
            account_numbers=[], account_open_date=None,
            monthly_income=None, employment_type=None,
            employer_name=None, existing_loans=[],
            documents_on_file=[], customer_segment=None,
            relationship_manager=None,
            risk_flag=None, fraud_flag=None,
            bounced_cheques_12m=None, avg_monthly_balance=None,
            failure_reason=None,   # not found = new customer, not an error
            timestamp=_now(),
        ).to_dict()

    return CustomerLookupResponse(
        found=True,
        customer_id=record["customer_id"],
        user_id=user_id,
        full_name=record["full_name"],
        email=record["email"],
        phone=record["phone"],
        date_of_birth=record["date_of_birth"],
        address=record["address"],
        pan_number=record["pan_number"],
        aadhaar_number=record["aadhaar_number"],
        kyc_status=record["kyc_status"],
        kyc_completed_date=record["kyc_completed_date"],
        account_numbers=record["account_numbers"],
        account_open_date=record["account_open_date"],
        monthly_income=record["monthly_income"],
        employment_type=record["employment_type"],
        employer_name=record["employer_name"],
        existing_loans=record["existing_loans"],
        documents_on_file=record["documents_on_file"],
        customer_segment=record["customer_segment"],
        relationship_manager=record["relationship_manager"],
        risk_flag=record.get("risk_flag", False),
        fraud_flag=record.get("fraud_flag", False),
        bounced_cheques_12m=record.get("bounced_cheques_12m", 0),
        avg_monthly_balance=record.get("avg_monthly_balance"),
        failure_reason=None,
        timestamp=_now(),
    ).to_dict()
