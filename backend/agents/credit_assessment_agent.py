"""
agents/credit_assessment_agent.py
=====================================
Final underwriting step in the LAP pipeline: pulls the customer's live
CIBIL score and affordability, and decides the loan amount/rate/EMI.
Works for any authenticated customer — PAN, salary, and existing EMIs
all come straight from their own bank_customers / existing_loans rows,
nothing hardcoded.
"""

from database.init_db import get_connection
from mock_api.mock_cibil_api import mock_cibil_api


def _generate_credit_reasoning(
    customer_name: str,
    cibil_score: int,
    cibil_rating: str,
    interest_rate: float,
    monthly_income: float,
    total_existing_emi: float,
    final_loan_eligible: float,
    monthly_emi_estimate: float,
    approved: bool,
) -> str:
    """LLM-generated natural language credit explanation. Returns None on failure."""
    try:
        from openai import AzureOpenAI
        from utils.config import (
            AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT,
            AZURE_OPENAI_API_VERSION, CHAT_DEPLOYMENT,
        )

        prompt = (
            "You are a senior bank credit analyst. "
            "Write a concise 3-4 sentence credit assessment explanation. "
            "Be professional and clear about the decision.\n\n"
            f"Customer: {customer_name}\n"
            f"CIBIL Score: {cibil_score} ({cibil_rating})\n"
            f"Monthly Income: Rs.{monthly_income:,.0f}\n"
            f"Existing EMI: Rs.{total_existing_emi:,.0f}\n"
            f"Interest Rate Offered: {interest_rate}%\n"
            f"Eligible Loan: Rs.{final_loan_eligible:,.0f}\n"
            f"Monthly EMI: Rs.{monthly_emi_estimate:,.0f}\n"
            f"Decision: {'Approved' if approved else 'Rejected'}\n\n"
            "Write directly, no headers. Start with CIBIL verdict."
        )

        _client = AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_version=AZURE_OPENAI_API_VERSION,
        )
        response = _client.chat.completions.create(
            model=CHAT_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Credit LLM reasoning failed: {e}")
        return None

# (min_score, rating, annual_rate_pct) — checked highest first
_SCORE_BANDS = [
    (750, "Excellent", 8.35),
    (700, "Good", 8.75),
    (650, "Fair", 9.25),
]

TENURE_YEARS = 20
TENURE_MONTHS = TENURE_YEARS * 12


def _failure(message: str) -> dict:
    return {
        "approved": False,
        "cibil_score": None,
        "cibil_rating": "Poor",
        "max_loan_by_income": 0,
        "final_loan_eligible": 0,
        "interest_rate": None,
        "tenure_years": TENURE_YEARS,
        "monthly_emi_estimate": 0,
        "summary": message,
    }


def assess_credit(
    customer_id: str,
    max_loan_from_property: float,
    approved_session_emi: float = 0,
) -> dict:
    """
    approved_session_emi: EMI of a loan already approved in this browser
    session (stored in session_store keyed by customer_id, not session_id,
    so it persists across New Application clicks). Stacks on top of the
    customer's database-recorded existing EMIs so a second back-to-back
    application is correctly constrained.
    """
    try:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT pan_number, monthly_income, full_name FROM bank_customers WHERE customer_id = ?",
                (customer_id,),
            )
            row = cursor.fetchone()
            if not row:
                return _failure("❌ Could not find customer record for credit assessment.")

            pan_number = row["pan_number"]
            monthly_income = row["monthly_income"] or 0
            customer_name = row["full_name"] or "Customer"

            cursor.execute(
                """
                SELECT SUM(emi) as total_emi FROM existing_loans
                WHERE customer_id = ? AND status = 'active'
                """,
                (customer_id,),
            )
            loan_row = cursor.fetchone()
            total_existing_emi = (loan_row["total_emi"] if loan_row else 0) or 0
        finally:
            conn.close()

        cibil = mock_cibil_api(pan_number)
        cibil_score = cibil.get("cibil_score") if cibil.get("success") else None
        if cibil_score is None:
            return _failure("❌ Could not retrieve a CIBIL score for this customer.")

        cibil_rating = "Poor"
        interest_rate = None
        approved = False
        for threshold, rating, rate in _SCORE_BANDS:
            if cibil_score >= threshold:
                cibil_rating, interest_rate, approved = rating, rate, True
                break

        if not approved:
            result = _failure(
                f"❌ Credit score {cibil_score} ({cibil_rating}) is below our minimum "
                f"threshold of 650 — application rejected."
            )
            result["cibil_score"] = cibil_score
            result["cibil_rating"] = cibil_rating
            return result

        # Stack previously-approved in-session EMI on top of DB-recorded ones
        effective_existing_emi = total_existing_emi + approved_session_emi
        available_emi = (monthly_income * 0.50) - effective_existing_emi
        if available_emi <= 0:
            extra_note = (
                f" (including recently approved loan EMI of ₹{approved_session_emi:,.0f})"
                if approved_session_emi > 0 else ""
            )
            result = _failure(
                f"❌ Unable to approve additional loan. Your total EMI obligations of "
                f"₹{effective_existing_emi:,.0f}/month{extra_note} already exceed "
                f"50% of your monthly income of ₹{monthly_income:,.0f}."
            )
            result["cibil_score"] = cibil_score
            result["cibil_rating"] = cibil_rating
            result["interest_rate"] = interest_rate
            return result

        r = (interest_rate / 100) / 12
        n = TENURE_MONTHS
        max_loan_by_income = available_emi * (((1 + r) ** n - 1) / (r * (1 + r) ** n))

        final_loan = min(max_loan_from_property or 0, max_loan_by_income)
        monthly_emi = final_loan * r * (1 + r) ** n / ((1 + r) ** n - 1)

        fallback_summary = (
            f"✅ Credit assessment approved! CIBIL Score: {cibil_score} ({cibil_rating}), "
            f"Interest Rate: {interest_rate}%, Eligible Loan: ₹{final_loan:,.0f}, "
            f"Estimated EMI: ₹{monthly_emi:,.0f}/month over {TENURE_YEARS} years."
        )
        llm_reasoning = _generate_credit_reasoning(
            customer_name=customer_name,
            cibil_score=cibil_score,
            cibil_rating=cibil_rating,
            interest_rate=interest_rate,
            monthly_income=monthly_income,
            total_existing_emi=effective_existing_emi,
            final_loan_eligible=final_loan,
            monthly_emi_estimate=monthly_emi,
            approved=True,
        )
        summary = f"{llm_reasoning}\n\n✅ Proceeding to final loan decision..." if llm_reasoning else fallback_summary

        return {
            "approved": True,
            "cibil_score": cibil_score,
            "cibil_rating": cibil_rating,
            "max_loan_by_income": round(max_loan_by_income, 2),
            "final_loan_eligible": round(final_loan, 2),
            "interest_rate": interest_rate,
            "tenure_years": TENURE_YEARS,
            "monthly_emi_estimate": round(monthly_emi, 2),
            "summary": summary,
        }
    except Exception as e:
        return _failure(f"❌ Credit assessment failed due to an internal error: {e}")
