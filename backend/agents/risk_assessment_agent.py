"""
agents/risk_assessment_agent.py
===================================
Risk scoring for the Loan Against Property pipeline. Pulls live values
from bank_customers / existing_loans for whichever customer_id is
passed in — works for any authenticated customer, nothing hardcoded.
"""

from database.init_db import get_connection


def _generate_risk_reasoning(
    customer_name: str,
    risk_level: str,
    risk_score: int,
    risk_flags: list,
    monthly_income: float,
    total_existing_emi: float,
    foir: float,
    avg_monthly_balance: float,
    fraud_flag: bool,
    bounced_cheques: int,
) -> str:
    """LLM-generated natural language risk explanation. Returns None on failure
    so the caller falls back to the existing rule-based summary."""
    try:
        from openai import AzureOpenAI
        from utils.config import (
            AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT,
            AZURE_OPENAI_API_VERSION, CHAT_DEPLOYMENT,
        )

        client = AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_version=AZURE_OPENAI_API_VERSION,
        )

        prompt = (
            "You are a senior bank risk analyst. "
            "Write a concise 3-4 sentence risk assessment explanation for this customer. "
            "Be professional but clear.\n\n"
            f"Customer: {customer_name}\n"
            f"Risk Level: {risk_level} (Score: {risk_score}/100)\n"
            f"Monthly Income: Rs.{monthly_income:,.0f}\n"
            f"Existing EMI: Rs.{total_existing_emi:,.0f}\n"
            f"FOIR: {foir:.1f}%\n"
            f"Average Balance: Rs.{avg_monthly_balance:,.0f}\n"
            f"Fraud Flag: {fraud_flag}\n"
            f"Bounced Cheques (12m): {bounced_cheques}\n"
            f"Risk Flags: {', '.join(risk_flags) if risk_flags else 'None'}\n\n"
            "Write the explanation directly, no headers or bullets. "
            "Start with the risk level verdict, then explain why."
        )

        response = client.chat.completions.create(
            model=CHAT_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Risk LLM reasoning failed: {e}")
        return None


def assess_risk(customer_id: str) -> dict:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT full_name, monthly_income, risk_flag, fraud_flag,
                   bounced_cheques_12m, avg_monthly_balance
            FROM bank_customers WHERE customer_id = ?
            """,
            (customer_id,),
        )
        row = cursor.fetchone()

        if not row:
            return {
                "risk_level": "high",
                "risk_score": 100,
                "approved": False,
                "risk_flags": ["customer_not_found"],
                "monthly_income": 0,
                "total_existing_emi": 0,
                "foir": 0,
                "summary": "❌ Could not find customer record for risk assessment.",
            }

        customer_name = row["full_name"] or "Customer"
        monthly_income = row["monthly_income"] or 0
        fraud_flag = bool(row["fraud_flag"])
        bounced_cheques_12m = row["bounced_cheques_12m"] or 0
        avg_monthly_balance = row["avg_monthly_balance"] or 0

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

    risk_flags = []
    score = 0

    if fraud_flag:
        score += 50
        risk_flags.append("fraud_flag")

    if bounced_cheques_12m > 2:
        score += 30
        risk_flags.append("bounced_cheques_high")
    elif bounced_cheques_12m > 0:
        score += 10
        risk_flags.append("bounced_cheques_present")

    foir = (total_existing_emi / monthly_income * 100) if monthly_income else 0
    if foir > 50:
        score += 25
        risk_flags.append("foir_high")

    if avg_monthly_balance < 10000:
        score += 15
        risk_flags.append("low_avg_balance")

    risk_level = "low" if score < 25 else "medium" if score < 50 else "high"
    approved = score < 50 and fraud_flag is False

    fallback_summary = (
        f"Risk Assessment — Monthly Income: ₹{monthly_income:,.0f}, "
        f"Existing EMI: ₹{total_existing_emi:,.0f}, FOIR: {foir:.1f}%, "
        f"Risk Score: {score}/100, Risk Level: {risk_level.upper()}. "
        + ("✅ Approved — proceeding to Credit Assessment..." if approved else "❌ Risk too high for approval at this time.")
    )

    llm_reasoning = _generate_risk_reasoning(
        customer_name=customer_name,
        risk_level=risk_level,
        risk_score=score,
        risk_flags=risk_flags,
        monthly_income=monthly_income,
        total_existing_emi=total_existing_emi,
        foir=foir,
        avg_monthly_balance=avg_monthly_balance,
        fraud_flag=fraud_flag,
        bounced_cheques=bounced_cheques_12m,
    )
    verdict = "✅ Approved — proceeding to Credit Assessment..." if approved else "❌ Risk too high for approval at this time."
    summary = f"{llm_reasoning}\n\n{verdict}" if llm_reasoning else fallback_summary

    return {
        "risk_level": risk_level,
        "risk_score": score,
        "approved": approved,
        "risk_flags": risk_flags,
        "monthly_income": monthly_income,
        "total_existing_emi": total_existing_emi,
        "foir": round(foir, 2),
        "summary": summary,
    }
