"""
mock_apis/mock_property_valuation_api.py
No file reads — all data comes from customer's uploaded documents.
Owner agent: property_verification_agent
Used in: Journey 2 (LAP), Journey 3 (External Home Loan)
Skipped in: Journey 1 (Bank Inventory)
"""
from __future__ import annotations
import datetime, hashlib
from typing import Optional
from dataclasses import dataclass, asdict

def _now(): return datetime.datetime.utcnow().isoformat() + "Z"

# ---------------------------------------------------------------------------
# Kolkata locality data — single source of truth.
# price_per_sqft  : market rate (always higher than govt circle rate used
#                   in mock_land_registry_api — realistic, stamp-duty vs market)
# ltv_recommended : base LTV cap before policy_rules.json deductions
# crime_score     : 0-100, lower is better → feeds policy "crime_score_above_60"
# flood_zone      : feeds policy "flood_zone" LTV deduction
# area_quality    : 0-100, higher is better → used in recommendation narrative
# appreciation    : 1yr % → determines market_trend
# ---------------------------------------------------------------------------
_KOLKATA_LOCALITIES: dict[str, dict] = {
    "alipore":       {"price_per_sqft": 15500, "ltv": 0.80, "crime_score": 14, "flood_zone": False, "area_quality": 95, "appreciation":  8.5},
    "ballygunge":    {"price_per_sqft": 13500, "ltv": 0.80, "crime_score": 17, "flood_zone": False, "area_quality": 91, "appreciation":  9.5},
    "park street":   {"price_per_sqft": 12500, "ltv": 0.75, "crime_score": 22, "flood_zone": False, "area_quality": 88, "appreciation":  7.5},
    "camac street":  {"price_per_sqft": 12000, "ltv": 0.75, "crime_score": 20, "flood_zone": False, "area_quality": 87, "appreciation":  7.5},
    "bhowanipore":   {"price_per_sqft": 11500, "ltv": 0.75, "crime_score": 20, "flood_zone": False, "area_quality": 87, "appreciation":  8.0},
    "lake gardens":  {"price_per_sqft": 11000, "ltv": 0.75, "crime_score": 21, "flood_zone": False, "area_quality": 86, "appreciation":  8.0},
    "salt lake":     {"price_per_sqft": 10500, "ltv": 0.75, "crime_score": 19, "flood_zone": False, "area_quality": 88, "appreciation": 10.0},
    "new town":      {"price_per_sqft":  9500, "ltv": 0.75, "crime_score": 21, "flood_zone": False, "area_quality": 85, "appreciation": 14.5},
    "rajarhat":      {"price_per_sqft":  8000, "ltv": 0.70, "crime_score": 24, "flood_zone": False, "area_quality": 80, "appreciation": 13.0},
    "em bypass":     {"price_per_sqft":  8500, "ltv": 0.75, "crime_score": 25, "flood_zone": False, "area_quality": 82, "appreciation":  9.0},
    "kasba":         {"price_per_sqft":  8000, "ltv": 0.75, "crime_score": 25, "flood_zone": False, "area_quality": 82, "appreciation":  9.0},
    "santoshpur":    {"price_per_sqft":  7500, "ltv": 0.70, "crime_score": 29, "flood_zone": False, "area_quality": 74, "appreciation":  7.5},
    "jadavpur":      {"price_per_sqft":  8500, "ltv": 0.75, "crime_score": 26, "flood_zone": False, "area_quality": 80, "appreciation": 11.0},
    "tollygunge":    {"price_per_sqft":  9000, "ltv": 0.75, "crime_score": 25, "flood_zone": False, "area_quality": 82, "appreciation": 10.5},
    "garia":         {"price_per_sqft":  7000, "ltv": 0.70, "crime_score": 30, "flood_zone": False, "area_quality": 76, "appreciation":  9.0},
    "narendrapur":   {"price_per_sqft":  6800, "ltv": 0.70, "crime_score": 28, "flood_zone": False, "area_quality": 74, "appreciation":  8.5},
    "lake town":     {"price_per_sqft":  6800, "ltv": 0.65, "crime_score": 33, "flood_zone": False, "area_quality": 72, "appreciation":  6.5},
    "dum dum":       {"price_per_sqft":  6200, "ltv": 0.65, "crime_score": 37, "flood_zone": False, "area_quality": 68, "appreciation":  6.0},
    "baranagar":     {"price_per_sqft":  6000, "ltv": 0.65, "crime_score": 38, "flood_zone": False, "area_quality": 66, "appreciation":  5.5},
    "barasat":       {"price_per_sqft":  5200, "ltv": 0.65, "crime_score": 41, "flood_zone": False, "area_quality": 61, "appreciation":  5.0},
    "shyambazar":    {"price_per_sqft":  7500, "ltv": 0.70, "crime_score": 35, "flood_zone": False, "area_quality": 70, "appreciation":  7.0},
    "ultadanga":     {"price_per_sqft":  7200, "ltv": 0.70, "crime_score": 36, "flood_zone": False, "area_quality": 68, "appreciation":  6.5},
    "entally":       {"price_per_sqft":  6800, "ltv": 0.60, "crime_score": 44, "flood_zone": False, "area_quality": 62, "appreciation":  6.0},
    "behala":        {"price_per_sqft":  5800, "ltv": 0.65, "crime_score": 38, "flood_zone": False, "area_quality": 65, "appreciation":  5.5},
    "thakurpukur":   {"price_per_sqft":  5200, "ltv": 0.60, "crime_score": 40, "flood_zone": False, "area_quality": 61, "appreciation":  4.5},
    "maheshtala":    {"price_per_sqft":  4800, "ltv": 0.60, "crime_score": 42, "flood_zone": False, "area_quality": 58, "appreciation":  4.0},
    "howrah":        {"price_per_sqft":  5500, "ltv": 0.65, "crime_score": 42, "flood_zone": True,  "area_quality": 62, "appreciation":  5.5},
    "shibpur":       {"price_per_sqft":  5200, "ltv": 0.60, "crime_score": 42, "flood_zone": True,  "area_quality": 62, "appreciation":  5.5},
    "liluah":        {"price_per_sqft":  4800, "ltv": 0.60, "crime_score": 46, "flood_zone": True,  "area_quality": 57, "appreciation":  4.5},
    "santragachi":   {"price_per_sqft":  4600, "ltv": 0.60, "crime_score": 48, "flood_zone": True,  "area_quality": 55, "appreciation":  4.0},
}
_DEFAULT_RATE        = 7000
_DEFAULT_LTV         = 0.70
_DEFAULT_CRIME       = 35
_DEFAULT_AREA_QUALITY= 70
_DEFAULT_APPRECIATION= 7.0


def _locality_from_address(address: str) -> str:
    addr = address.lower()
    # check longer/more-specific keys first to avoid "howrah" matching
    # before "shibpur" when both appear (substring safety)
    for loc in sorted(_KOLKATA_LOCALITIES, key=len, reverse=True):
        if loc in addr:
            return loc
    return ""


def _simulate(pincode: str, area_sqft: int) -> dict:
    """
    Deterministic fallback for genuinely unknown pincode + no locality match.
    Tightened to 5000-7999 — realistic 'average Kolkata suburb' range,
    never exceeding known premium-area rates.
    """
    seed = int(hashlib.md5(pincode.encode()).hexdigest(), 16)
    price_per_sqft = 5000 + (seed % 3000)              # 5000-7999
    appreciation   = round(4.0 + (seed % 8), 1)        # 4.0-11.9
    trend = "rising" if appreciation >= 7 else ("stable" if appreciation >= 4 else "falling")
    ltv   = 0.70 if trend == "rising" else (0.65 if trend == "stable" else 0.60)
    return {
        "price_per_sqft":       price_per_sqft,
        "market_value":         price_per_sqft * area_sqft,
        "appreciation_pct_1yr": appreciation,
        "market_trend":         trend,
        "ltv_recommended":      ltv,
        "crime_score":          _DEFAULT_CRIME + (seed % 10),     # 35-44
        "flood_zone":           (seed % 12) == 0,                  # ~8% chance
        "area_quality_score":   _DEFAULT_AREA_QUALITY - (seed % 10),# 61-70
        "locality":             "Kolkata (unmapped area)",
        "comparable_transactions": [],
        "valuer_name":          "PropValue Analytics Pvt Ltd",
        "is_simulated":         True,
    }


# Demo records — keyed by pincode, matching the 5 test scenarios.
# Pulls base rate/ltv/crime/flood/area_quality from _KOLKATA_LOCALITIES
# but pins comparable_transactions for realism.
_VALUATION_DB: dict[str, dict] = {
    "700019": {  # Ballygunge — approved path
        "locality": "ballygunge",
        "comparable_transactions": [
            {"address": "22B, Ballygunge Place", "value": 15500000, "date": "2024-10-05"},
            {"address": "37, Gariahat Road",      "value": 16200000, "date": "2024-12-01"},
        ],
    },
    "700089": {  # Lake Town — disputed, borderline
        "locality": "lake town",
        "comparable_transactions": [
            {"address": "14, Lake Town Block A", "value": 6200000, "date": "2024-09-18"},
        ],
    },
    "700156": {  # New Town — new customer approved path
        "locality": "new town",
        "comparable_transactions": [
            {"address": "Block AA-1, New Town", "value": 12000000, "date": "2024-11-12"},
            {"address": "Action Area II, NKDA", "value": 11500000, "date": "2024-12-20"},
        ],
    },
    "700028": {  # Dum Dum — partial mortgage, borderline
        "locality": "dum dum",
        "comparable_transactions": [
            {"address": "Dum Dum Park, Block C", "value": 5500000, "date": "2024-08-30"},
        ],
    },
    "700014": {  # Entally — invalid registry, auto-reject path
        "locality": "entally",
        "comparable_transactions": [
            {"address": "Entally Market Road", "value": 5000000, "date": "2024-07-15"},
        ],
    },
}


def _build_result(loc_key: str, area_sqft: int, comps: list, simulated: bool) -> dict:
    loc = _KOLKATA_LOCALITIES.get(loc_key, {})
    price_per_sqft = loc.get("price_per_sqft", _DEFAULT_RATE)
    appreciation   = loc.get("appreciation", _DEFAULT_APPRECIATION)
    trend = "rising" if appreciation >= 7 else ("stable" if appreciation >= 4 else "falling")
    ltv   = loc.get("ltv", _DEFAULT_LTV)
    if trend == "falling":
        ltv = max(ltv - 0.05, 0.50)
    return {
        "price_per_sqft":       price_per_sqft,
        "market_value":         price_per_sqft * area_sqft,
        "appreciation_pct_1yr": appreciation,
        "market_trend":         trend,
        "ltv_recommended":      ltv,
        "crime_score":          loc.get("crime_score", _DEFAULT_CRIME),
        "flood_zone":           loc.get("flood_zone", False),
        "area_quality_score":   loc.get("area_quality", _DEFAULT_AREA_QUALITY),
        "locality":             loc_key or "Kolkata",
        "comparable_transactions": comps,
        "valuer_name":          "PropValue Analytics Pvt Ltd",
        "is_simulated":         simulated,
    }


@dataclass
class ValuationResponse:
    success: bool
    address: str
    pincode: str
    locality: str
    area_sqft: int
    property_type: str
    market_value: int                  # price_per_sqft × area_sqft
    price_per_sqft: int
    valuation_method: str
    comparable_transactions: list
    appreciation_pct_1yr: float
    market_trend: str                  # "rising" | "stable" | "falling"
    ltv_recommended: float             # post-trend-adjustment LTV cap
    crime_score: int                   # 0-100, lower better — policy LTV deduction input
    flood_zone: bool                   # policy LTV deduction input
    area_quality_score: int            # 0-100, higher better — for recommendation narrative
    valuation_date: str
    valuer_name: str
    is_simulated: bool                 # True if pincode/locality not in known data
    failure_reason: Optional[str]
    timestamp: str

    def to_dict(self): return asdict(self)


def mock_property_valuation_api(
    address: str,
    pincode: str,
    area_sqft: int,
    property_type: str,
) -> dict:
    """
    Get market valuation + area risk scores for a customer-owned property.
    Input comes entirely from the customer's uploaded documents.
    No JSON file is read — this simulates an external valuation API.

    Parameters
    ----------
    address       : full property address from Sale Deed
    pincode       : 6-digit pincode from Sale Deed
    area_sqft     : built-up area from Sale Deed
    property_type : e.g. "residential_apartment", "villa", "plot"

    Returns
    -------
    ValuationResponse as dict.
    market_value      = price_per_sqft × area_sqft
    ltv_recommended   = base LTV cap (already adjusted for falling trend).
                        eligibility_agent applies further deductions from
                        policy_rules.json["ltv_policy"]["ltv_deductions"]
                        using crime_score and flood_zone below.
    crime_score > 60  → triggers "crime_score_above_60" deduction (-0.05)
    flood_zone = True → triggers "flood_zone" deduction (-0.10)
    is_simulated=True → pincode/locality unmapped, add note to state

    Lookup priority
    ---------------
    1. pincode in _VALUATION_DB           → exact demo match
    2. locality keyword found in address  → _KOLKATA_LOCALITIES match
    3. neither found                      → deterministic simulation

    Demo pincodes
    -------------
    700019 → Ballygunge  rising  ltv=0.80  crime=17  flood=False (approved)
    700156 → New Town    rising  ltv=0.75  crime=21  flood=False (new customer)
    700089 → Lake Town   stable  ltv=0.65  crime=33  flood=False (borderline)
    700028 → Dum Dum     stable  ltv=0.65  crime=37  flood=False (borderline)
    700014 → Entally     stable  ltv=0.60  crime=44  flood=False (reject path)
    Any other pincode → checks address for locality keyword,
                        else deterministic simulation (is_simulated=True)
    """
    if not address or not pincode or not area_sqft:
        return ValuationResponse(
            success=False,
            address=address or "", pincode=pincode or "", locality="",
            area_sqft=area_sqft or 0, property_type=property_type or "",
            market_value=0, price_per_sqft=0,
            valuation_method="", comparable_transactions=[],
            appreciation_pct_1yr=0.0, market_trend="",
            ltv_recommended=0.0, crime_score=0, flood_zone=False,
            area_quality_score=0, valuation_date=_now()[:10],
            valuer_name="", is_simulated=False,
            failure_reason="Missing required fields: address, pincode, area_sqft",
            timestamp=_now(),
        ).to_dict()

    demo = _VALUATION_DB.get(pincode)
    if demo:
        result = _build_result(demo["locality"], area_sqft, demo["comparable_transactions"], simulated=False)
    else:
        locality = _locality_from_address(address)
        if locality:
            result = _build_result(locality, area_sqft, [], simulated=True)
        else:
            result = _simulate(pincode, area_sqft)

    return ValuationResponse(
        success=True,
        address=address,
        pincode=pincode,
        locality=result["locality"],
        area_sqft=area_sqft,
        property_type=property_type,
        market_value=result["market_value"],
        price_per_sqft=result["price_per_sqft"],
        valuation_method="comparable_sales",
        comparable_transactions=result["comparable_transactions"],
        appreciation_pct_1yr=result["appreciation_pct_1yr"],
        market_trend=result["market_trend"],
        ltv_recommended=result["ltv_recommended"],
        crime_score=result["crime_score"],
        flood_zone=result["flood_zone"],
        area_quality_score=result["area_quality_score"],
        valuation_date=_now()[:10],
        valuer_name=result["valuer_name"],
        is_simulated=result["is_simulated"],
        failure_reason=None,
        timestamp=_now(),
    ).to_dict()
