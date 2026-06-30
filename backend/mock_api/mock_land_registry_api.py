"""
mock_apis/mock_land_registry_api.py
No file reads — all data comes from customer's uploaded documents.
Owner agent: property_verification_agent
Used in: Journey 2 (LAP), Journey 3 (External Home Loan)
Skipped in: Journey 1 (Bank Inventory)
"""
from __future__ import annotations
import datetime, hashlib
from typing import Optional
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher

def _now(): return datetime.datetime.utcnow().isoformat() + "Z"

def _name_match(a: str, b: str) -> bool:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio() >= 0.80

# Kolkata locality → government circle rate (₹/sqft)
_KOLKATA_RATES = {
    "alipore": 13000, "ballygunge": 11000, "park street": 10500,
    "camac street": 10000, "bhowanipore": 9500, "lake gardens": 9000,
    "salt lake": 8500, "new town": 7500, "rajarhat": 6500,
    "em bypass": 7000, "kasba": 6500, "santoshpur": 6000,
    "lake town": 5500, "dum dum": 5000, "baranagar": 4800,
    "barasat": 4200, "behala": 4800, "thakurpukur": 4200,
    "maheshtala": 4000, "howrah": 4500, "shibpur": 4300,
    "liluah": 4000, "santragachi": 3800, "garia": 5800,
    "narendrapur": 5500, "jadavpur": 7000, "tollygunge": 7500,
    "entally": 5500, "shyambazar": 6000, "ultadanga": 5800,
}
_DEFAULT_RATE = 5500   # Kolkata average fallback

def _rate_from_address(address: str) -> int:
    addr = address.lower()
    for locality, rate in _KOLKATA_RATES.items():
        if locality in addr:
            return rate
    return _DEFAULT_RATE

def _simulate(reg_no: str, owner_name: str, owner_pan: str, address: str) -> dict:
    """Deterministic simulation for any WB registration number."""
    seed = int(hashlib.md5(reg_no.encode()).hexdigest(), 16)
    area  = 600 + (seed % 1801)                          # 600–2400 sqft
    year  = 2010 + (seed % 14)
    month = 1 + (seed % 12)
    day   = 1 + (seed % 28)
    rate  = _rate_from_address(address)
    govt_value = int(area * rate * (0.85 + (seed % 30) / 100))
    is_joint  = (seed % 5) == 0
    disputed  = (seed % 10) == 0
    clear     = (seed % 8) != 0
    mortgage  = "clear" if clear else ("partially_released" if seed % 2 else "mortgaged")
    return {
        "owner_name": owner_name, "owner_pan": owner_pan,
        "co_owners": [{"name": "Co-owner", "share_pct": 50}] if is_joint else [],
        "ownership_type": "joint" if is_joint else "sole",
        "registration_date": f"{year}-{month:02d}-{day:02d}",
        "area_sqft": area, "property_type": "residential_apartment",
        "locality": "Kolkata", "pincode": "700000",
        "legal_disputes": disputed,
        "dispute_details": "Manual verification required" if disputed else None,
        "mortgage_status": mortgage,
        "mortgaged_bank": None if clear else "Unknown Bank",
        "encumbrance_clear": clear, "registry_valid": True,
        "government_value": govt_value,
    }

# Demo records — Kolkata WB registrations matching test scenarios
_REGISTRY_DB: dict[str, dict] = {
    "WB-REG-2019-004521": {   # clean, sole owner, Ballygunge — approved path
        "owner_name":"Rajesh Kumar Das","owner_pan":"ABCRD1234F","co_owners":[],
        "ownership_type":"sole","registration_date":"2019-03-14","area_sqft":1150,
        "property_type":"residential_apartment","locality":"Ballygunge","pincode":"700019",
        "legal_disputes":False,"dispute_details":None,"mortgage_status":"clear",
        "mortgaged_bank":None,"encumbrance_clear":True,"registry_valid":True,
        "government_value":9800000,
    },
    "WB-REG-2017-008834": {   # joint, disputed, mortgaged — rejected path
        "owner_name":"Priya Sengupta","owner_pan":"BFGPS5678K",
        "co_owners":[{"name":"Arjun Sengupta","share_pct":50}],
        "ownership_type":"joint","registration_date":"2017-09-22","area_sqft":920,
        "property_type":"residential_apartment","locality":"Lake Town","pincode":"700089",
        "legal_disputes":True,"dispute_details":"Boundary dispute — civil suit CS/KOL/2022/00445 pending",
        "mortgage_status":"mortgaged","mortgaged_bank":"SBI",
        "encumbrance_clear":False,"registry_valid":True,"government_value":6200000,
    },
    "WB-REG-2021-011209": {   # clean, new customer, New Town — approved path
        "owner_name":"Sunita Ghosh","owner_pan":"DIPSG3456Q","co_owners":[],
        "ownership_type":"sole","registration_date":"2021-06-30","area_sqft":1280,
        "property_type":"residential_apartment","locality":"New Town","pincode":"700156",
        "legal_disputes":False,"dispute_details":None,"mortgage_status":"clear",
        "mortgaged_bank":None,"encumbrance_clear":True,"registry_valid":True,
        "government_value":8400000,
    },
    "WB-REG-2016-003367": {   # joint, partial mortgage — borderline path
        "owner_name":"Amir Sheikh","owner_pan":"CHQAS9012P",
        "co_owners":[{"name":"Nasreen Sheikh","share_pct":50}],
        "ownership_type":"joint","registration_date":"2016-04-11","area_sqft":890,
        "property_type":"residential_apartment","locality":"Dum Dum","pincode":"700028",
        "legal_disputes":False,"dispute_details":None,
        "mortgage_status":"partially_released","mortgaged_bank":"PNB",
        "encumbrance_clear":False,"registry_valid":True,"government_value":5100000,
    },
    "WB-REG-2020-000001": {   # invalid registry, court stay — auto-reject path
        "owner_name":"Debashis Roy","owner_pan":"EJQDR7890R","co_owners":[],
        "ownership_type":"sole","registration_date":"2020-02-28","area_sqft":740,
        "property_type":"residential_apartment","locality":"Entally","pincode":"700014",
        "legal_disputes":True,
        "dispute_details":"Title dispute — court stay on all transactions (CS/KOL/2021/00891)",
        "mortgage_status":"mortgaged","mortgaged_bank":"HDFC Bank",
        "encumbrance_clear":False,"registry_valid":False,"government_value":4800000,
    },
}

@dataclass
class LandRegistryResponse:
    success: bool
    registration_number: str
    address: str
    owner_name: Optional[str]
    owner_pan: Optional[str]
    co_owners: list
    ownership_type: Optional[str]
    ownership_verified: bool
    co_owner_consent_required: bool
    co_owner_consent_obtained: bool
    registration_date: Optional[str]
    area_sqft: Optional[int]
    property_type: Optional[str]
    locality: Optional[str]
    pincode: Optional[str]
    legal_disputes: Optional[bool]
    dispute_details: Optional[str]
    mortgage_status: Optional[str]     # "clear"|"mortgaged"|"partially_released"
    mortgaged_bank: Optional[str]
    encumbrance_clear: Optional[bool]
    registry_valid: Optional[bool]
    government_value: Optional[int]
    failure_reason: Optional[str]
    timestamp: str
    def to_dict(self): return asdict(self)

def mock_land_registry_api(registration_number: str, owner_name: str,
                            owner_pan: str, address: str) -> dict:
    """
    Verify property ownership and legal status.
    Input comes entirely from the customer's uploaded documents.
    No JSON file is read — this simulates an external government API.

    Parameters
    ----------
    registration_number : WB-REG-YYYY-XXXXXX from customer's sale deed
    owner_name          : from sale deed
    owner_pan           : from KYC
    address             : full property address

    Returns
    -------
    LandRegistryResponse as dict.
    ownership_verified=False     → rejection
    legal_disputes=True          → escalation
    mortgage_status="mortgaged"  → need NOC from existing lender
    registry_valid=False         → auto-rejection
    co_owner_consent_required=True → agent must collect co-owner sign-off

    Demo registration numbers
    -------------------------
    WB-REG-2019-004521 → clean, Ballygunge       (approved)
    WB-REG-2021-011209 → clean, New Town         (new customer approved)
    WB-REG-2016-003367 → partial mortgage, Dum Dum (borderline)
    WB-REG-2017-008834 → disputed + mortgaged    (rejected)
    WB-REG-2020-000001 → invalid registry        (auto-reject)
    Any other WB-REG-* → deterministic simulation based on address
    """
    # owner_pan is intentionally NOT required here — Flow 2B (own-choice
    # purchase) verifies the seller's title and typically never collects
    # the seller's PAN, only their name from the Sale Deed.
    if not registration_number or not owner_name:
        return LandRegistryResponse(
            success=False, registration_number=registration_number or "",
            address=address or "", owner_name=None, owner_pan=None, co_owners=[],
            ownership_type=None, ownership_verified=False,
            co_owner_consent_required=False, co_owner_consent_obtained=False,
            registration_date=None, area_sqft=None, property_type=None,
            locality=None, pincode=None, legal_disputes=None, dispute_details=None,
            mortgage_status=None, mortgaged_bank=None, encumbrance_clear=None,
            registry_valid=None, government_value=None,
            failure_reason="Missing required fields: registration_number, owner_name",
            timestamp=_now(),
        ).to_dict()

    rec = _REGISTRY_DB.get(registration_number) or _simulate(registration_number, owner_name, owner_pan, address)

    ownership_verified = _name_match(rec["owner_name"], owner_name) or rec["owner_pan"] == owner_pan
    co_owner_consent_required = len(rec["co_owners"]) > 0

    return LandRegistryResponse(
        success=True, registration_number=registration_number, address=address,
        owner_name=rec["owner_name"], owner_pan=rec["owner_pan"],
        co_owners=rec["co_owners"], ownership_type=rec["ownership_type"],
        ownership_verified=ownership_verified,
        co_owner_consent_required=co_owner_consent_required,
        co_owner_consent_obtained=False,
        registration_date=rec["registration_date"], area_sqft=rec["area_sqft"],
        property_type=rec["property_type"], locality=rec.get("locality","Kolkata"),
        pincode=rec.get("pincode","700000"),
        legal_disputes=rec["legal_disputes"], dispute_details=rec["dispute_details"],
        mortgage_status=rec["mortgage_status"], mortgaged_bank=rec["mortgaged_bank"],
        encumbrance_clear=rec["encumbrance_clear"], registry_valid=rec["registry_valid"],
        government_value=rec["government_value"],
        failure_reason=None, timestamp=_now(),
    ).to_dict()
