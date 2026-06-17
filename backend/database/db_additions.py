"""
database/db_additions.py
=========================
Run this ONCE to add the pending_registrations table
to your existing banking.db.

This table stores temporary records for new users
who are in the middle of OTP verification before KYC.

How to run:
    python database/db_additions.py
"""

from init_db import get_connection


def add_pending_registrations_table():
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_registrations (
                temp_id     TEXT PRIMARY KEY,
                phone       TEXT UNIQUE NOT NULL,
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
        print("✅ pending_registrations table added.")
    finally:
        conn.close()


if __name__ == "__main__":
    add_pending_registrations_table()
