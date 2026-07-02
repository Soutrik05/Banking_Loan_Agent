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


def _generate_decision_message(
    customer_name: str,
    decision: str,
    loan_amount: float,
    interest_rate: float,
    monthly_emi: float,
    rejection_reasons: list,
    property_locality: str,
    employer_name: str,
) -> str:
    """LLM-generated personalised closing message for the loan decision card.
    Returns None on failure so the caller silently skips it."""
    try:
        from openai import AzureOpenAI
        from utils.config import (
            AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT,
            AZURE_OPENAI_API_VERSION, CHAT_DEPLOYMENT,
        )

        if decision == "approved":
            prompt = (
                "You are a bank relationship manager. "
                "Write a warm, professional 2-3 sentence congratulations message "
                "for a customer whose home loan was approved. "
                "Be genuine and mention specific details.\n\n"
                f"Customer: {customer_name}\n"
                f"Employer: {employer_name or 'their organisation'}\n"
                f"Loan Amount: Rs.{loan_amount:,.0f}\n"
                f"Interest Rate: {interest_rate}%\n"
                f"Monthly EMI: Rs.{monthly_emi:,.0f}\n"
                f"Property: {property_locality or 'the selected property'}\n\n"
                "Write directly, conversational tone."
            )
        elif decision == "rejected":
            prompt = (
                "You are a bank relationship manager. "
                "Write an empathetic 2-3 sentence message explaining the loan rejection. "
                "Be honest but supportive. Mention that help is available.\n\n"
                f"Customer: {customer_name}\n"
                f"Rejection Reasons: {', '.join(rejection_reasons)}\n\n"
                "Write directly, empathetic tone."
            )
        else:
            prompt = (
                "You are a bank relationship manager. "
                "Write a 2-3 sentence message for a conditional loan approval. "
                "Explain that conditions need to be met before disbursement.\n\n"
                f"Customer: {customer_name}\n"
                f"Conditions: {', '.join(rejection_reasons)}\n\n"
                "Write directly, professional tone."
            )

        _client = AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_version=AZURE_OPENAI_API_VERSION,
        )
        response = _client.chat.completions.create(
            model=CHAT_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Decision LLM message failed: {e}")
        return None


def make_loan_decision(
    property_result: dict,
    risk_result: dict,
    credit_result: dict,
    customer_name: str,
    flow_type: str = "lap",
    purchase_price: float = None,
    employer_name: str = "",
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
            "flow_type": flow_type,  # "lap" | "own_choice" | "tie_ups"
            "loan_amount": credit_result.get("final_loan_eligible"),
            "interest_rate": credit_result.get("interest_rate"),
            "tenure_years": 20,
            "monthly_emi": credit_result.get("monthly_emi_estimate"),
            "cibil_score": credit_result.get("cibil_score"),
            "cibil_rating": credit_result.get("cibil_rating"),
            "property_value": property_result.get("government_value"),
            "conditions": conditions,
            "rejection_reasons": rejection_reasons,
            "purchase_price": purchase_price if flow_type == "own_choice" else None,
        }

        llm_message = _generate_decision_message(
            customer_name=customer_name,
            decision=decision,
            loan_amount=credit_result.get("final_loan_eligible") or 0,
            interest_rate=credit_result.get("interest_rate") or 0,
            monthly_emi=credit_result.get("monthly_emi_estimate") or 0,
            rejection_reasons=rejection_reasons or conditions,
            property_locality=property_result.get("address", ""),
            employer_name=employer_name,
        )
        if llm_message:
            display_card["personalized_message"] = llm_message

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
