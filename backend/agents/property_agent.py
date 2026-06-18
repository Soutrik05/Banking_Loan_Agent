"""
agents/property_agent.py
===========================
Two paths:
  LAP (Loan Against Property) — customer owns a property, uploads Sale Deed
       → mock_land_registry_api + mock_property_valuation_api → full verification
  Home Loan (Bank Inventory) — customer picks from bank's pre-verified list
       → fast track, skips risk_assessment + credit_assessment per policy
"""

import json
from pathlib import Path
from mock_api.mock_land_registry_api import mock_land_registry_api
from mock_api.mock_property_valuation_api import mock_property_valuation_api
from session_store import mark_step

_PROPERTIES_PATH = Path(__file__).resolve().parent.parent / "mock_data" / "properties.json"


def _load_bank_inventory() -> dict:
    with open(_PROPERTIES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["bank_inventory"]


def get_property_choice_message() -> dict:
    return {
        "message": (
            "Are you looking to take a loan against a property you already own, "
            "or would you like to buy a new property using our loan?"
        ),
        "type": "mcq",
        "options": [
            {"id": "lap", "label": "I own a property", "next_step": "lap_upload"},
            {"id": "home_loan", "label": "I want to buy a property", "next_step": "show_inventory"},
        ],
    }


def submit_own_property(
    session_id: str,
    registration_number: str,
    owner_name: str,
    owner_pan: str,
    address: str,
    pincode: str,
    area_sqft: int,
    property_type: str = "residential_apartment",
) -> dict:
    mark_step(session_id, "property", "active", set_active=True)

    registry = mock_land_registry_api(
        registration_number=registration_number,
        owner_name=owner_name,
        owner_pan=owner_pan,
        address=address,
    )

    if not registry["success"]:
        mark_step(session_id, "property", "failed")
        return {"success": False, "message": registry.get("failure_reason", "Property verification failed."), "next_step": None}

    valuation = mock_property_valuation_api(
        address=address, pincode=pincode, area_sqft=area_sqft, property_type=property_type,
    )

    flags = []
    if not registry["ownership_verified"]: flags.append("ownership_name_mismatch")
    if registry.get("co_owner_consent_required") and not registry.get("co_owner_consent_obtained"):
        flags.append("co_owner_consent_pending")
    if registry["legal_disputes"]: flags.append("legal_dispute")
    if registry["mortgage_status"] != "clear": flags.append("existing_mortgage")
    if not registry["encumbrance_clear"]: flags.append("encumbrance_not_clear")
    if not registry.get("registry_valid", True): flags.append("registry_invalid")
    if valuation.get("is_simulated"): flags.append("valuation_unverified_locality")

    max_loan_eligible = int(valuation["market_value"] * valuation["ltv_recommended"])

    if "registry_invalid" in flags or "ownership_name_mismatch" in flags:
        next_step, status = "rejected", "failed"
        message = "There's an issue verifying ownership or the registry record. A specialist will reach out to you directly."
    elif "legal_dispute" in flags or "co_owner_consent_pending" in flags or "existing_mortgage" in flags or "encumbrance_not_clear" in flags:
        next_step, status = "inspection_required", "active"
        message = "A few details on this property need manual review — we'll schedule a quick inspection before moving forward."
    else:
        next_step, status = "risk_assessment", "completed"
        message = (
            f"Verified! Your property is valued at ₹{valuation['market_value']:,}, "
            f"which means you could be eligible for up to ₹{max_loan_eligible:,}. "
            f"Let's check your eligibility next."
        )

    mark_step(session_id, "property", status)

    return {
        "success": True,
        "flags": flags,
        "market_value": valuation["market_value"],
        "max_loan_eligible": max_loan_eligible,
        "ltv_recommended": valuation["ltv_recommended"],
        "message": message,
        "next_step": next_step,
    }


def get_bank_inventory(city: str = None, max_price: int = None) -> dict:
    inventory = _load_bank_inventory()
    results = []
    for pid, rec in inventory.items():
        if city and rec["city"].lower() != city.lower(): continue
        if max_price and rec["listed_price"] > max_price: continue
        results.append({
            "property_id": pid, "address": rec["address"], "city": rec["city"],
            "area_sqft": rec["area_sqft"], "bedrooms": rec["bedrooms"],
            "listed_price": rec["listed_price"], "down_payment_min": rec["down_payment_min"],
            "max_loan_available": rec["max_loan_available"], "property_score": rec["property_score"],
            "nearby_schools": rec.get("nearby_schools"),
            "hospitals": rec.get("hospitals"),
            "transit": rec.get("transit"),
            "crime_rate": rec.get("crime_rate"),
        })
    return {"success": True, "properties": results, "count": len(results)}


def select_bank_property(session_id: str, property_id: str) -> dict:
    inventory = _load_bank_inventory()
    rec = inventory.get(property_id)
    if not rec:
        return {"success": False, "message": f"Property '{property_id}' not found.", "next_step": None}

    mark_step(session_id, "property", "completed")

    return {
        "success": True,
        "property": rec,
        "fast_track": True,
        "max_loan_eligible": rec["max_loan_available"],
        "message": (
            f"Great pick! {rec['address']} is priced at ₹{rec['listed_price']:,}. "
            f"Since this is one of our own properties, you're fast-tracked — "
            f"no extra verification needed. Minimum down payment: ₹{rec['down_payment_min']:,}."
        ),
        "next_step": "loan_eligibility",
    }
