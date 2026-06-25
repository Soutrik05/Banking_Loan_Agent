"""
agents/property_verification_agent.py
=========================================
Verifies a Sale Deed against the (mock) land registry and decides
whether the property qualifies as collateral for a Loan Against
Property (LAP). Registration number, owner details and address all
come from the customer's uploaded document — works for any customer,
any property, nothing hardcoded.
"""

from mock_api.mock_land_registry_api import mock_land_registry_api


def verify_property(
    registration_number: str,
    owner_name: str,
    owner_pan: str,
    address: str,
    area_sqft: int = None,
) -> dict:
    result = mock_land_registry_api(
        registration_number=registration_number,
        owner_name=owner_name,
        owner_pan=owner_pan,
        address=address,
    )

    if not result.get("success"):
        reason = result.get("failure_reason") or "Could not verify this property."
        return {
            "verified": False,
            "status": "rejected",
            "government_value": None,
            "max_loan_eligible": None,
            "rejection_reasons": [reason],
            "summary": f"❌ Verification failed. {reason}",
        }

    rejection_reasons = []
    status = "approved"

    if result.get("registry_valid") is False:
        rejection_reasons.append("Registry invalid or court stay")
        status = "rejected"

    if result.get("ownership_verified") is False:
        rejection_reasons.append("Owner mismatch")
        status = "rejected"

    if result.get("legal_disputes") is True:
        rejection_reasons.append("Active legal dispute")
        if status != "rejected":
            status = "manual_review"

    if result.get("mortgage_status") == "mortgaged":
        rejection_reasons.append("NOC required from existing lender")
        if status != "rejected":
            status = "manual_review"

    govt_value = result.get("government_value") or 0
    max_loan_eligible = int(govt_value * 0.65)  # 65% LTV for LAP

    if status == "approved":
        summary = (
            f"✅ Property verified! Government Value: ₹{govt_value:,}, "
            f"Max Loan: ₹{max_loan_eligible:,}. Proceeding to Risk Assessment..."
        )
    elif status == "manual_review":
        summary = f"⚠️ Manual review needed. {', '.join(rejection_reasons)}"
    else:
        summary = f"❌ Verification failed. {', '.join(rejection_reasons)}"

    return {
        "verified": status == "approved",
        "status": status,
        "government_value": govt_value,
        "max_loan_eligible": max_loan_eligible,
        "rejection_reasons": rejection_reasons,
        "summary": summary,
        # Registry-confirmed property details, passed through so downstream
        # steps (e.g. the valuation agent) don't have to re-derive them.
        "address": result.get("address") or address,
        "area_sqft": result.get("area_sqft") or area_sqft,
        "property_type": result.get("property_type"),
        "registration_number": registration_number,
    }
