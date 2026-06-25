"""
agents/loan_decision_agent.py
=================================
Final aggregation step of the LAP pipeline: combines the property
verification, risk assessment, and credit assessment results into one
loan decision plus a JSON "card" payload the frontend renders. Works
for any customer — every field comes from the three result dicts and
the customer_name passed in, nothing hardcoded.
"""

import json


def make_loan_decision(
    property_result: dict,
    risk_result: dict,
    credit_result: dict,
    customer_name: str,
) -> dict:
    try:
        rejection_reasons: list = []
        conditions: list = []

        if property_result.get("status") == "rejected":
            rejection_reasons.extend(property_result.get("rejection_reasons", []))
        elif property_result.get("status") == "manual_review":
            conditions.extend(property_result.get("rejection_reasons", []))

        if not risk_result.get("approved", False):
            rejection_reasons.append("Risk assessment did not meet approval criteria")

        if not credit_result.get("approved", False):
            rejection_reasons.append(
                credit_result.get("summary") or "Credit assessment did not meet approval criteria"
            )

        if rejection_reasons:
            decision = "rejected"
        elif conditions:
            decision = "conditional"
        else:
            decision = "approved"

        display_card = {
            "decision": decision,
            "customer_name": customer_name,
            "loan_amount": credit_result.get("final_loan_eligible"),
            "interest_rate": credit_result.get("interest_rate"),
            "tenure_years": 20,
            "monthly_emi": credit_result.get("monthly_emi_estimate"),
            "cibil_score": credit_result.get("cibil_score"),
            "cibil_rating": credit_result.get("cibil_rating"),
            "property_value": property_result.get("government_value"),
            "conditions": conditions,
            "rejection_reasons": rejection_reasons,
        }

        return {
            "decision": decision,
            "display_card": display_card,
            "summary": "LOAN_DECISION_CARD:" + json.dumps(display_card),
        }
    except Exception as e:
        display_card = {
            "decision": "rejected",
            "customer_name": customer_name,
            "conditions": [],
            "rejection_reasons": [f"Internal error while finalising decision: {e}"],
        }
        return {
            "decision": "rejected",
            "display_card": display_card,
            "summary": "LOAN_DECISION_CARD:" + json.dumps(display_card),
        }
