"""
database/init_db.py
====================
Creates all SQLite tables and migrates data from customers.json.
Run once: python database/init_db.py
"""

import sqlite3
import hashlib
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "banking.db")


def get_connection():
    """Returns a SQLite connection. Used by all agents."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # allows dict-style access
    return conn


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def create_tables(conn):
    cursor = conn.cursor()

    # ── Users table (login credentials) ──────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id         TEXT PRIMARY KEY,
            password_hash   TEXT NOT NULL,
            full_name       TEXT NOT NULL,
            email           TEXT UNIQUE,
            phone           TEXT UNIQUE NOT NULL,
            role            TEXT DEFAULT 'customer',
            is_active       INTEGER DEFAULT 1,
            created_at      TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now'))
        )
    """)

    # ── Bank customers table (KYC & profile) ─────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bank_customers (
            customer_id         TEXT PRIMARY KEY,
            user_id             TEXT NOT NULL REFERENCES users(user_id),
            full_name           TEXT NOT NULL,
            email               TEXT,
            phone               TEXT,
            date_of_birth       TEXT,
            address             TEXT,
            pan_number          TEXT UNIQUE,
            aadhaar_number      TEXT,
            kyc_status          TEXT DEFAULT 'pending',
            kyc_completed_date  TEXT,
            monthly_income      REAL,
            employment_type     TEXT,
            employer_name       TEXT,
            customer_segment    TEXT DEFAULT 'standard',
            relationship_manager TEXT,
            risk_flag           INTEGER DEFAULT 0,
            fraud_flag          INTEGER DEFAULT 0,
            bounced_cheques_12m INTEGER DEFAULT 0,
            avg_monthly_balance REAL,
            created_at          TEXT DEFAULT (datetime('now'))
        )
    """)

    # ── OTP table ─────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS otp_store (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT NOT NULL REFERENCES users(user_id),
            phone       TEXT NOT NULL,
            otp_code    TEXT NOT NULL,
            purpose     TEXT DEFAULT 'login',
            is_used     INTEGER DEFAULT 0,
            expires_at  TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)

    # ── JWT sessions table ────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id      TEXT PRIMARY KEY,
            user_id         TEXT NOT NULL REFERENCES users(user_id),
            jwt_token       TEXT NOT NULL,
            is_active       INTEGER DEFAULT 1,
            created_at      TEXT DEFAULT (datetime('now')),
            expires_at      TEXT NOT NULL,
            last_used_at    TEXT DEFAULT (datetime('now'))
        )
    """)

    # ── Existing loans table ──────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS existing_loans (
            loan_id             TEXT PRIMARY KEY,
            customer_id         TEXT NOT NULL REFERENCES bank_customers(customer_id),
            loan_type           TEXT,
            outstanding_amount  REAL,
            emi                 REAL,
            status              TEXT DEFAULT 'active'
        )
    """)

    conn.commit()
    print("✅ Tables created successfully.")


def migrate_from_json(conn):
    """Migrates data from customers.json into SQLite."""
    json_path = os.path.join(
        os.path.dirname(__file__), "../mock_data/customers.json"
    )

    with open(json_path, "r") as f:
        data = json.load(f)

    cursor = conn.cursor()
    HASH = hash_password("password123")  # reset all passwords to password123

    # ── Insert users ──────────────────────────────────────────────────────
    for user_id, user in data["users"].items():
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO users
                    (user_id, password_hash, full_name, email, phone, role, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                HASH,
                user["full_name"],
                user["email"],
                user["phone"].replace("+91-", "+91"),
                user["role"],
                1 if user["is_active"] else 0,
            ))
        except Exception as e:
            print(f"  ⚠️  User {user_id}: {e}")

    # ── Insert bank customers ─────────────────────────────────────────────
    for user_id, bc in data.get("bank_customers", {}).items():
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO bank_customers
                    (customer_id, user_id, full_name, email, phone,
                     date_of_birth, address, pan_number, aadhaar_number,
                     kyc_status, kyc_completed_date, monthly_income,
                     employment_type, employer_name, customer_segment,
                     relationship_manager, risk_flag, fraud_flag,
                     bounced_cheques_12m, avg_monthly_balance)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                bc["customer_id"], user_id, bc["full_name"],
                bc["email"], bc["phone"], bc["date_of_birth"],
                bc["address"], bc["pan_number"], bc["aadhaar_number"],
                bc["kyc_status"], bc.get("kyc_completed_date"),
                bc["monthly_income"], bc["employment_type"],
                bc["employer_name"], bc["customer_segment"],
                bc["relationship_manager"],
                1 if bc["risk_flag"] else 0,
                1 if bc["fraud_flag"] else 0,
                bc["bounced_cheques_12m"], bc["avg_monthly_balance"],
            ))

            # Insert existing loans
            for loan in bc.get("existing_loans", []):
                cursor.execute("""
                    INSERT OR IGNORE INTO existing_loans
                        (loan_id, customer_id, loan_type, outstanding_amount, emi, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    loan["loan_id"], bc["customer_id"],
                    loan["type"], loan["outstanding_amount"],
                    loan["emi"], loan["status"],
                ))
        except Exception as e:
            print(f"  ⚠️  Bank customer {user_id}: {e}")

    conn.commit()
    print("✅ Data migrated from customers.json successfully.")
    print("   All passwords set to: password123")


def verify_migration(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM bank_customers")
    customers = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM existing_loans")
    loans = cursor.fetchone()[0]
    print(f"\n📊 Database summary:")
    print(f"   Users          : {users}")
    print(f"   Bank customers : {customers}")
    print(f"   Existing loans : {loans}")


if __name__ == "__main__":
    print("🚀 Initialising banking database...")
    conn = get_connection()
    create_tables(conn)
    migrate_from_json(conn)
    verify_migration(conn)
    conn.close()
    print(f"\n✅ Database ready at: {DB_PATH}")
