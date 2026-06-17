"""
mock_apis/mock_fraud_detection_api.py
Reads: customers.json → ["fraud_signals"]
Owner agent: risk_assessment_agent
"""
from __future__ import annotations
import datetime, hashlib
from typing import Optional
from dataclasses import dataclass, asdict
from ._data_loader import load_json

def _now(): return datetime.datetime.utcnow().isoformat() + "Z"

@dataclass
class FraudDetectionResponse:
    success: bool
    customer_id: str
    fraud_flag: Optional[bool]
    fraud_confidence: Optional[float]
    risk_signals: list
    identity_verified: Optional[bool]
    blacklist_match: Optional[bool]
    synthetic_identity_score: Optional[float]
    document_tampering_detected: Optional[bool]
    previous_fraud_claims: Optional[int]
    device_risk: Optional[str]
    ip_risk: Optional[str]
    failure_reason: Optional[str]
    timestamp: str
    def to_dict(self): return asdict(self)

def _simulate_new_customer_signals(customer_id: str) -> dict:
    """
    For new customers not yet in fraud_signals,
    generate a deterministic low-risk profile.
    New customers have no fraud history by definition.
    Seed ensures same customer_id always returns same result.
    """
    seed = int(hashlib.md5(customer_id.encode()).hexdigest(), 16)
    confidence = round(0.02 + (seed % 12) / 100, 2)   # 0.02 – 0.13
    return {
        "fraud_flag": False,
        "fraud_confidence": confidence,
        "risk_signals": [],
        "identity_verified": True,
        "blacklist_match": False,
        "synthetic_identity_score": round(confidence * 0.8, 2),
        "document_tampering_detected": False,
        "previous_fraud_claims": 0,
        "device_risk": "low",
        "ip_risk": "low",
    }

def mock_fraud_detection_api(customer_id: str) -> dict:
    """
    Run fraud risk analysis for a customer.

    Reads from: customers.json → ["fraud_signals"]

    Parameters
    ----------
    customer_id : bank customer ID e.g. "CUST001"
                  for new customers pass a session-generated ID

    Returns
    -------
    FraudDetectionResponse as dict.
    fraud_flag=True        → route immediately to escalation_agent
    blacklist_match=True   → auto-reject (S30 edge case)
    success=False          → customer_id missing entirely

    Fix over original
    -----------------
    Was reading from separate fraud_signals.json (did not exist).
    Now reads from customers.json → ["fraud_signals"].
    New customers not in the section get a deterministic
    low-risk simulated profile instead of a failure response.
    """
    if not customer_id:
        return FraudDetectionResponse(
            success=False, customer_id="",
            fraud_flag=None, fraud_confidence=None,
            risk_signals=["missing_customer_id"],
            identity_verified=None, blacklist_match=None,
            synthetic_identity_score=None,
            document_tampering_detected=None,
            previous_fraud_claims=None,
            device_risk=None, ip_risk=None,
            failure_reason="customer_id is required",
            timestamp=_now(),
        ).to_dict()

    data = load_json("customers.json")
    rec = data.get("fraud_signals", {}).get(customer_id)

    # not in fraud_signals = new customer = simulate clean profile
    if not rec:
        rec = _simulate_new_customer_signals(customer_id)

    return FraudDetectionResponse(
        success=True,
        customer_id=customer_id,
        fraud_flag=rec["fraud_flag"],
        fraud_confidence=rec["fraud_confidence"],
        risk_signals=rec["risk_signals"],
        identity_verified=rec["identity_verified"],
        blacklist_match=rec["blacklist_match"],
        synthetic_identity_score=rec["synthetic_identity_score"],
        document_tampering_detected=rec["document_tampering_detected"],
        previous_fraud_claims=rec["previous_fraud_claims"],
        device_risk=rec["device_risk"],
        ip_risk=rec["ip_risk"],
        failure_reason=None,
        timestamp=_now(),
    ).to_dict()
