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


def verify_seller_property(
    registration_number: str,
    seller_name: str,
    address: str,
    area_sqft: int = None,
) -> dict:
    """
    For Flow 2B (Own Choice) — verifies the SELLER's ownership is
    legitimate, not the customer's. The customer is the buyer here, not
    expected to match the owner name in the registry, so (unlike
    verify_property above) ownership_verified is never checked against
    the customer — only the property's legal/registry/mortgage status.

    Seller PAN typically isn't extracted from a Sale Deed the customer
    uploads, so it's omitted entirely (mock_land_registry_api no longer
    requires it).
    """
    result = mock_land_registry_api(
        registration_number=registration_number,
        owner_name=seller_name,
        owner_pan="",
        address=address,
    )

    if not result.get("success"):
        reason = result.get("failure_reason") or "Could not verify this property."
        return {
            "verified": False,
            "status": "rejected",
            "government_value": None,
            "rejection_reasons": [reason],
            "land_registry_result": result,
            "summary": f"❌ Verification failed. {reason}",
        }

    rejection_reasons = []
    status = "approved"

    if not result.get("registry_valid"):
        rejection_reasons.append("Seller's property registry is invalid")
        status = "rejected"

    if result.get("legal_disputes"):
        rejection_reasons.append(
            f"Active legal dispute on this property: "
            f"{result.get('dispute_details') or 'details unavailable'}"
        )
        status = "manual_review" if status != "rejected" else "rejected"

    if result.get("mortgage_status") == "mortgaged":
        rejection_reasons.append(
            "Property is currently mortgaged - seller must "
            "provide NOC from existing lender before sale"
        )
        status = "manual_review" if status != "rejected" else "rejected"

    govt_value = result.get("government_value") or 0

    summary = _build_seller_verification_summary(status, rejection_reasons, govt_value)

    return {
        "verified": status == "approved",
        "status": status,
        "government_value": govt_value,
        "rejection_reasons": rejection_reasons,
        "land_registry_result": result,
        "summary": summary,
        # Registry-confirmed property details, passed through so downstream
        # steps (e.g. the valuation agent) don't have to re-derive them.
        "address": result.get("address") or address,
        "area_sqft": result.get("area_sqft") or area_sqft,
        "property_type": result.get("property_type"),
        "registration_number": registration_number,
    }


def _build_seller_verification_summary(status: str, reasons: list, govt_value: int) -> str:
    if status == "approved":
        return (
            f"✅ Property ownership verified successfully.\n\n"
            f"Seller's title is clear and the property has no legal encumbrances.\n"
            f"Government Value: ₹{govt_value:,}\n\n"
            f"Proceeding to property valuation..."
        )
    elif status == "manual_review":
        return (
            f"⚠️ Property requires manual review before purchase.\n\n"
            + "\n".join(f"- {r}" for r in reasons)
        )
    else:
        return (
            f"❌ Property verification failed.\n\n"
            + "\n".join(f"- {r}" for r in reasons)
        )
