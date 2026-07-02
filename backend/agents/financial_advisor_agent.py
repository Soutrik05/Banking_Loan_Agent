"""
agents/financial_advisor_agent.py
====================================
LLM-powered personal financial advisor. Has full read-only access to the
customer's live financial profile (income, loans, accounts, balances) and
answers ANY financial query — from vague ("I am broke") to precise
("Should I break my FD to prepay the loan?"). Works for any customer;
nothing here is hardcoded to a specific person.
"""

import os
from openai import AzureOpenAI
from database.init_db import get_connection
from utils.config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_VERSION,
    CHAT_DEPLOYMENT,
)

_client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version=AZURE_OPENAI_API_VERSION,
)


def get_customer_financial_context(customer_id: str) -> dict:
    """Fetch all relevant financial data for the customer from the database."""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT full_name, monthly_income, employment_type, employer_name,
                   avg_monthly_balance, customer_segment, bounced_cheques_12m,
                   pan_number, account_numbers
            FROM bank_customers
            WHERE customer_id = ?
            """,
            (customer_id,),
        )
        row = cursor.fetchone()
        profile = dict(row) if row else {}

        cursor.execute(
            """
            SELECT loan_id, loan_type, outstanding_amount, emi, status
            FROM existing_loans
            WHERE customer_id = ? AND status = 'active'
            """,
            (customer_id,),
        )
        loans = [dict(r) for r in cursor.fetchall()]

        raw_accounts = profile.pop("account_numbers", "") or ""
        accounts = [a.strip() for a in raw_accounts.split(",") if a.strip()]

        return {
            "profile": profile,
            "existing_loans": loans,
            "accounts": accounts,
            "total_existing_emi": sum(l.get("emi") or 0 for l in loans),
        }
    finally:
        conn.close()


def _build_system_prompt(context: dict, loan_decision: dict = None) -> str:
    """Build a comprehensive system prompt containing the customer's real
    financial data so every advisor response is grounded in actual numbers."""
    profile = context["profile"]
    loans = context["existing_loans"]
    accounts = context["accounts"]
    total_emi = context["total_existing_emi"]
    monthly_income = profile.get("monthly_income") or 0

    fd_accounts = [a for a in accounts if a.upper().startswith("FD")]
    sb_accounts = [a for a in accounts if not a.upper().startswith("FD")]

    foir = (total_emi / monthly_income * 100) if monthly_income else 0
    surplus = max(0, monthly_income - total_emi)

    loan_lines = "\n".join(
        f"  - {l.get('loan_type', 'Loan')} (ID {l.get('loan_id', '?')}): "
        f"EMI Rs.{(l.get('emi') or 0):,.0f}/month, "
        f"Outstanding Rs.{(l.get('outstanding_amount') or 0):,.0f}"
        for l in loans
    ) if loans else "  No active loans."

    system = f"""You are a personal financial advisor at National Bank.
You have full access to the customer's live financial profile and must give
accurate, personalised advice based on their REAL numbers — never invent figures.

CUSTOMER PROFILE
Name            : {profile.get('full_name', 'Customer')}
Monthly Income  : Rs.{monthly_income:,.0f}
Employer        : {profile.get('employer_name', 'Unknown')}
Employment Type : {profile.get('employment_type', 'Unknown')}
Avg Monthly Bal : Rs.{(profile.get('avg_monthly_balance') or 0):,.0f}
Segment         : {profile.get('customer_segment', 'standard')}

LINKED ACCOUNTS
Savings : {', '.join(sb_accounts) if sb_accounts else 'None'}
FDs     : {', '.join(fd_accounts) if fd_accounts else 'None'}

EXISTING LOAN OBLIGATIONS
{loan_lines}
Total EMI Burden: Rs.{total_emi:,.0f}/month
FOIR            : {foir:.1f}%
Monthly Surplus : Rs.{surplus:,.0f}
"""

    if loan_decision and isinstance(loan_decision, dict):
        card = loan_decision.get("display_card") or loan_decision
        system += f"""
RECENT LOAN APPLICATION
Decision     : {card.get('decision', 'N/A').upper()}
Loan Amount  : Rs.{(card.get('loan_amount') or 0):,.0f}
Interest Rate: {card.get('interest_rate', '—')}%
Monthly EMI  : Rs.{(card.get('monthly_emi') or 0):,.0f}
CIBIL Score  : {card.get('cibil_score', 'N/A')}
"""

    system += """
YOUR ROLE
- Answer ANY financial question the customer asks using their REAL numbers.
- Handle vague queries empathetically ("I am broke", "I need help") —
  acknowledge their concern, then surface concrete options from their data.
- Specific questions (FD breaking, prepayment, tenure change): do the actual
  maths using the figures above.
- For CIBIL improvement: give specific, timeline-bound steps.
- For co-applicant queries: explain eligibility impact with numbers.
- Keep responses concise — 3-5 sentences or a short numbered list.
- Use Rs. for all currency amounts. Never use generic placeholders like "your income".
- If something is not in the customer's best interest, say so honestly.
- Always suggest at least one actionable next step.
"""
    return system


def get_financial_advice(
    customer_id: str,
    user_message: str,
    conversation_history: list,
    loan_decision: dict = None,
) -> str:
    """
    Main entry point for the financial advisor.

    Args:
        customer_id: Authenticated customer's ID.
        user_message: The customer's latest question.
        conversation_history: Previous advisor-conversation turns
            (list of {"role": "user"|"assistant", "content": "..."}).
        loan_decision: Most recent loan decision result dict (optional).

    Returns:
        Advisor's response as a plain string.
    """
    try:
        context = get_customer_financial_context(customer_id)
        system_prompt = _build_system_prompt(context, loan_decision)

        messages = [{"role": "system", "content": system_prompt}]
        for turn in conversation_history[-10:]:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": user_message})

        response = _client.chat.completions.create(
            model=CHAT_DEPLOYMENT,
            messages=messages,
            max_tokens=300,
            temperature=0.5,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"Financial advisor error: {e}")
        return (
            "I'm having trouble accessing your financial details right now. "
            "Please try again in a moment, or speak to our relationship "
            "manager for immediate assistance."
        )
