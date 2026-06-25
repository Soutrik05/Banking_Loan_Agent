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


def assess_credit(customer_id: str, max_loan_from_property: float) -> dict:
    try:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT pan_number, monthly_income FROM bank_customers WHERE customer_id = ?",
                (customer_id,),
            )
            row = cursor.fetchone()
            if not row:
                return _failure("❌ Could not find customer record for credit assessment.")

            pan_number = row["pan_number"]
            monthly_income = row["monthly_income"] or 0

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

        available_emi = (monthly_income * 0.50) - total_existing_emi
        if available_emi <= 0:
            result = _failure(
                f"❌ Existing EMI obligations leave no room for an additional loan "
                f"(available EMI capacity: ₹{available_emi:,.0f})."
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

        summary = (
            f"✅ Credit assessment approved! CIBIL Score: {cibil_score} ({cibil_rating}), "
            f"Interest Rate: {interest_rate}%, Eligible Loan: ₹{final_loan:,.0f}, "
            f"Estimated EMI: ₹{monthly_emi:,.0f}/month over {TENURE_YEARS} years."
        )

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
