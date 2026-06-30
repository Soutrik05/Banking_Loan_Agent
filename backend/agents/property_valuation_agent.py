"""
Property Valuation Agent
Simulates bank-appointed technical valuation.
Uses locality rates from mock_land_registry_api._KOLKATA_RATES
"""

# Import locality rates from existing mock API
from mock_api.mock_land_registry_api import _KOLKATA_RATES, _DEFAULT_RATE


def valuate_property(
    area_sqft: int,
    address: str,
    property_type: str,
    registration_number: str,
    government_value: int,
    ltv_ratio: float = 0.65,
    purchase_price: int = None,
) -> dict:
    """
    Simulates technical valuation by bank-appointed valuer.

    ltv_ratio defaults to 0.65 (LAP, against distress value) for backward
    compatibility. Flow 2B (own-choice purchase) passes ltv_ratio=0.80 and
    its own purchase_price, which additionally caps the loan — a bank
    will never lend more than the LTV share of what the customer is
    actually paying, even if its own valuation comes in higher.

    Returns:
    {
        "fair_market_value": int,
        "distress_value": int,
        "max_loan": int,            # ltv_ratio of distress value, capped by purchase_price if given
        "max_loan_lap": int,        # 65% of distress value (kept for existing LAP callers/UI)
        "max_loan_home": int,       # 80% of fair market value
        "locality": str,
        "locality_rate_per_sqft": int,
        "area_sqft": int,
        "valuation_grade": str,     # "A" | "B" | "C"
        "summary": str,
        "approved": bool
    }
    """
    # Detect locality from address
    address_lower = (address or "").lower()
    locality = "Kolkata"
    locality_rate = _DEFAULT_RATE

    for loc, rate in _KOLKATA_RATES.items():
        if loc in address_lower:
            locality = loc.title()
            locality_rate = rate
            break

    # Calculate values
    fair_market_value = int((area_sqft or 0) * locality_rate)

    # Use higher of calculated vs government value
    # (government circle rate is minimum floor)
    fair_market_value = max(fair_market_value, government_value or 0)

    # Distress/forced sale value = 85% of fair market
    distress_value = int(fair_market_value * 0.85)

    # Max loan amounts
    max_loan_lap = int(distress_value * 0.65)     # LAP: 65% of distress (kept for existing UI)
    max_loan_home = int(fair_market_value * 0.80)  # Home loan: 80% of FMV

    # Generalized max loan at the caller's LTV ratio — also capped by the
    # purchase price when one is given (own-choice flow), since the bank
    # will never lend more than the LTV share of the actual sale price.
    max_loan_by_ltv = int(distress_value * ltv_ratio)
    if purchase_price:
        max_loan_by_purchase_price = int(purchase_price * ltv_ratio)
        max_loan = min(max_loan_by_ltv, max_loan_by_purchase_price)
    else:
        max_loan = max_loan_by_ltv

    # Valuation grade based on locality rate
    if locality_rate >= 8000:
        grade = "A"
        grade_desc = "Prime Location"
    elif locality_rate >= 5500:
        grade = "B"
        grade_desc = "Good Location"
    else:
        grade = "C"
        grade_desc = "Standard Location"

    summary = _build_valuation_summary(
        locality, locality_rate, area_sqft,
        fair_market_value, distress_value,
        max_loan, ltv_ratio, grade, grade_desc,
        capped_by_purchase_price=bool(purchase_price),
    )

    return {
        "fair_market_value": fair_market_value,
        "distress_value": distress_value,
        "max_loan": max_loan,
        "max_loan_lap": max_loan_lap,
        "max_loan_home": max_loan_home,
        "ltv_ratio": ltv_ratio,
        "locality": locality,
        "locality_rate_per_sqft": locality_rate,
        "area_sqft": area_sqft,
        "valuation_grade": grade,
        "valuation_grade_desc": grade_desc,
        "summary": summary,
        "approved": True
    }


def _build_valuation_summary(locality, rate, area, fmv, distress, max_loan, ltv_ratio, grade, grade_desc, capped_by_purchase_price=False):
    cap_note = ", capped to the stated purchase price," if capped_by_purchase_price else ""
    return (
        f"🏠 Technical Valuation Complete\n\n"
        f"**Locality:** {locality} ({grade_desc})\n"
        f"**Circle Rate:** ₹{rate:,}/sq.ft.\n"
        f"**Total Area:** {area} sq.ft.\n\n"
        f"**Fair Market Value:** ₹{fmv:,}\n"
        f"**Distress Value (85%):** ₹{distress:,}\n"
        f"**Maximum Loan Eligible:** ₹{max_loan:,}\n"
        f"*({int(ltv_ratio * 100)}% of distress value{cap_note} as per RBI guidelines)*\n\n"
        f"Valuation Grade: **{grade}** — {grade_desc}\n\n"
        f"Proceeding to Risk Assessment..."
    )
