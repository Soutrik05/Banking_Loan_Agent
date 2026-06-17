"""
agents/account_discovery_agent.py
===================================
Called immediately after successful login (existing customer only).

Checks if the logged-in user has a bank_customers record.
Loads their full profile into the conversation state.
Decides what to ask next — property question.

New users never reach this agent — they go to kyc_agent after OTP.
"""

from database.init_db import get_connection


def discover_account(user_id: str, customer_id: str) -> dict:
    """
    Load existing customer's full profile from DB.

    Called after existing_verify_otp() returns next_step="account_discovery"

    Parameters
    ----------
    user_id     : from JWT payload
    customer_id : from JWT payload

    Returns
    -------
    {
        success          : bool,
        is_existing      : bool,
        customer_id      : str,
        full_name        : str,
        pan_number       : str,
        aadhaar_number   : str,
        kyc_status       : str,
        monthly_income   : float,
        employment_type  : str,
        employer_name    : str,
        existing_loans   : list,
        total_emi        : float,
        avg_balance      : float,
        customer_segment : str,
        risk_flag        : bool,
        fraud_flag       : bool,
        documents_on_file: list,
        message          : str,
        next_step        : "property_question"
    }
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Load bank customer profile
        cursor.execute("""
            SELECT bc.*
            FROM bank_customers bc
            WHERE bc.customer_id = ? AND bc.user_id = ?
        """, (customer_id, user_id))
        bc = cursor.fetchone()

        if not bc:
            return {
                "success": False,
                "is_existing": False,
                "message": "No bank customer record found for this user.",
                "next_step": None,
            }

        # Load existing loans
        cursor.execute("""
            SELECT loan_id, loan_type, outstanding_amount, emi, status
            FROM existing_loans
            WHERE customer_id = ?
        """, (customer_id,))
        loans = [dict(row) for row in cursor.fetchall()]
        total_emi = sum(l["emi"] for l in loans if l["status"] == "active")

        # Documents on file — derived from kyc_status
        docs_on_file = []
        if bc["kyc_status"] == "verified":
            docs_on_file = ["aadhaar", "pan", "salary_slip", "bank_statement"]

        return {
            "success": True,
            "is_existing": True,
            "customer_id": bc["customer_id"],
            "full_name": bc["full_name"],
            "email": bc["email"],
            "phone": bc["phone"],
            "date_of_birth": bc["date_of_birth"],
            "address": bc["address"],
            "pan_number": bc["pan_number"],
            "aadhaar_number": bc["aadhaar_number"],
            "kyc_status": bc["kyc_status"],
            "monthly_income": bc["monthly_income"],
            "employment_type": bc["employment_type"],
            "employer_name": bc["employer_name"],
            "existing_loans": loans,
            "total_emi": total_emi,
            "avg_balance": bc["avg_monthly_balance"],
            "customer_segment": bc["customer_segment"],
            "risk_flag": bool(bc["risk_flag"]),
            "fraud_flag": bool(bc["fraud_flag"]),
            "documents_on_file": docs_on_file,
            "message": (
                f"Welcome back, {bc['full_name']}! "
                f"We have your records on file. "
                f"No need to re-submit any documents."
            ),
            "next_step": "property_question",
        }

    except Exception as e:
        return {
            "success": False,
            "is_existing": False,
            "message": str(e),
            "next_step": None,
        }
    finally:
        conn.close()


def get_property_question(full_name: str) -> str:
    """
    Returns the property question the bot asks after account discovery.
    Called by the UI/orchestrator to get the next bot message.
    """
    return (
        f"Great {full_name}! Now let's get started with your loan. "
        f"Are you looking to take a loan against a property you already own, "
        f"or are you looking to buy a new property using our loan?"
    )
