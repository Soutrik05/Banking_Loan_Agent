"""
services/ocr_service.py
==========================
DEMO MODE — no real OCR call. Simulates document processing with a short
delay, then returns the logged-in customer's own bank record as if it had
been read straight off their uploaded Sale Deed.

Works for any customer_id: the three seeded demo customers map to the
scripted mock_land_registry_api entries (so the verification → risk
pipeline always produces a consistent, presentable result for them);
anyone else gets a freshly generated registration number paired with
their real DB details.
"""

import random
import time

from database.init_db import get_connection

# customer_id -> registration_number, matching the scripted entries in
# mock_land_registry_api._REGISTRY_DB.
_DEMO_REGISTRATION_NUMBERS = {
    "CUST001": "WB-REG-2019-004521",  # Rajesh — clean, approved path
    "CUST002": "WB-REG-2017-008834",  # Priya — disputed + mortgaged, manual review
    "CUST003": "WB-REG-2021-011209",  # Sunita — clean, new-customer approved path
}

_DEMO_AREA_SQFT = {
    "CUST001": 1150,
    "CUST002": 920,
    "CUST003": 1280,
}


def _random_registration_number() -> str:
    year = random.randint(2015, 2023)
    serial = random.randint(100000, 999999)
    return f"WB-REG-{year}-{serial:06d}"


def extract_sale_deed_fields(file_bytes: bytes, filename: str, customer_id: str = None) -> dict:
    time.sleep(2)  # simulate OCR/processing latency

    owner_name = None
    owner_pan = None
    address = None

    if customer_id:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT full_name, pan_number, address FROM bank_customers WHERE customer_id = ?",
                (customer_id,),
            )
            row = cursor.fetchone()
            if row:
                owner_name = row["full_name"]
                owner_pan = row["pan_number"]
                address = row["address"]
        finally:
            conn.close()

    registration_number = _DEMO_REGISTRATION_NUMBERS.get(customer_id) or _random_registration_number()
    area_sqft = _DEMO_AREA_SQFT.get(customer_id, random.randint(900, 1800))

    extracted_fields = {
        "registration_number": registration_number,
        "owner_name": owner_name,
        "owner_pan": owner_pan,
        "address": address,
        "area_sqft": area_sqft,
        "property_type": "residential_apartment",
    }

    return {
        "success": True,
        "extracted_fields": extracted_fields,
        "message": "Fields extracted successfully",
    }
