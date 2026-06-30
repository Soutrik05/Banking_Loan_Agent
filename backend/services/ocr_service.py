"""
services/ocr_service.py
==========================
Real document text extraction — pdfplumber first (fast, accurate for
digital PDFs), Tesseract OCR as a fallback (scanned PDFs / photographed
documents). No simulation, no per-customer hardcoding: extraction works
identically for any customer's any document, across all three flows
(LAP Sale Deed, inherited/gifted multi-document, own-choice purchase
documents).
"""

import io
import os
import re
from typing import Optional

import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image

# On Windows local dev, Tesseract may not be on PATH — allow an explicit
# override. On Render/Docker (see Dockerfile), tesseract-ocr is installed
# system-wide and already on PATH, so this is a no-op there.
TESSERACT_CMD = os.getenv("TESSERACT_CMD")
if TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


def extract_text_pdfplumber(file_bytes: bytes) -> str:
    """Extract text directly from a digital PDF (fast, accurate)."""
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            text = ""
            for page in pdf.pages[:3]:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text.strip()
    except Exception as e:
        print(f"pdfplumber extraction failed: {e}")
        return ""


def extract_text_tesseract(file_bytes: bytes, filename: str) -> str:
    """Fallback: OCR via Tesseract for scanned PDFs or image uploads."""
    try:
        ext = filename.lower().rsplit(".", 1)[-1]
        if ext == "pdf":
            images = convert_from_bytes(file_bytes, dpi=200, first_page=1, last_page=2)
        else:
            images = [Image.open(io.BytesIO(file_bytes))]

        text = ""
        for img in images:
            text += pytesseract.image_to_string(img) + "\n"
        return text.strip()
    except Exception as e:
        print(f"Tesseract OCR failed: {e}")
        return ""


def parse_fields_from_text(raw_text: str) -> dict:
    """
    Parse structured fields from extracted text using regex.
    Works across Sale Deed, Gift Deed, Succession Certificate,
    Mutation Certificate, Encumbrance Certificate, and NOC documents.
    """
    fields = {
        "registration_number": None,
        "owner_name": None,
        "owner_pan": None,
        "address": None,
        "area_sqft": None,
        "property_type": None,
        "document_type": None,
    }

    text = raw_text

    # Registration Number: WB-REG-YYYY-XXXXXX
    reg_match = re.search(r'(WB-REG-\d{4}-\d{6})', text, re.IGNORECASE)
    if reg_match:
        fields["registration_number"] = reg_match.group(1).upper()

    # Document type detection
    if re.search(r'deed of sale|sale deed', text, re.IGNORECASE):
        fields["document_type"] = "sale_deed"
    elif re.search(r'deed of gift|gift deed', text, re.IGNORECASE):
        fields["document_type"] = "gift_deed"
    elif re.search(r'succession certificate', text, re.IGNORECASE):
        fields["document_type"] = "succession_certificate"
    elif re.search(r'mutation certificate', text, re.IGNORECASE):
        fields["document_type"] = "mutation_certificate"
    elif re.search(r'encumbrance certificate', text, re.IGNORECASE):
        fields["document_type"] = "encumbrance_certificate"
    elif re.search(r'no objection certificate', text, re.IGNORECASE):
        fields["document_type"] = "noc"

    # PAN: 5 letters + 4 digits + 1 letter
    pan_matches = re.findall(r'\b([A-Z]{5}\d{4}[A-Z])\b', text)
    owner_keywords = ["purchaser", "owner name", "successor name", "recipient", "new owner", "full name"]
    found_pan = None
    for keyword in owner_keywords:
        idx = text.lower().find(keyword)
        if idx != -1:
            nearby = text[idx:idx + 300]
            m = re.search(r'\b([A-Z]{5}\d{4}[A-Z])\b', nearby)
            if m:
                found_pan = m.group(1)
                break
    fields["owner_pan"] = found_pan or (pan_matches[0] if pan_matches else None)

    # Owner Name
    name_patterns = re.findall(
        r'(?:Full Name|Owner Name|Successor Name)\s*:\s*([A-Za-z\s\.]+?)(?:\n|PAN|Address)',
        text, re.IGNORECASE
    )
    if name_patterns:
        # Prefer the name nearest a purchaser/owner/recipient/successor keyword
        chosen_name = None
        for keyword in ["purchaser", "owner", "successor", "recipient", "new owner"]:
            idx = text.lower().find(keyword)
            if idx != -1:
                section = text[idx:idx + 400]
                sub = re.search(
                    r'(?:Full Name|Owner Name|Successor Name)\s*:\s*([A-Za-z\s\.]+?)(?:\n|PAN|Address)',
                    section, re.IGNORECASE
                )
                if sub:
                    chosen_name = sub.group(1).strip()
                    break
        fields["owner_name"] = chosen_name or name_patterns[0].strip()

    # Address (prefer one with a pincode or "Kolkata")
    addr_matches = re.findall(r'(?:Property Address|Address)\s*:\s*([^\n]+)', text, re.IGNORECASE)
    if addr_matches:
        chosen_addr = None
        for addr in addr_matches:
            if re.search(r'\d{6}', addr) or 'kolkata' in addr.lower():
                chosen_addr = addr.strip()
                break
        fields["address"] = chosen_addr or addr_matches[0].strip()

    # Area
    area_match = re.search(r'(?:Total Area|Area)\s*:\s*([\d,]+)\s*sq\.?\s*ft', text, re.IGNORECASE)
    if area_match:
        fields["area_sqft"] = int(area_match.group(1).replace(",", ""))

    # Property Type
    if re.search(r'residential\s*apartment', text, re.IGNORECASE):
        fields["property_type"] = "residential_apartment"
    elif re.search(r'commercial', text, re.IGNORECASE):
        fields["property_type"] = "commercial"
    elif re.search(r'land', text, re.IGNORECASE):
        fields["property_type"] = "land"

    return fields


def extract_sale_deed_fields(file_bytes: bytes, filename: str, customer_id: Optional[str] = None) -> dict:
    """
    Main entry point for document OCR extraction. Used for every property
    document across all flows (Sale Deed, Gift Deed, Succession
    Certificate, Mutation Certificate, Encumbrance Certificate, NOC).

    customer_id is accepted for logging/storage purposes only — it plays
    no role in extraction; the result depends solely on what's actually
    in the uploaded document.
    """
    try:
        raw_text = extract_text_pdfplumber(file_bytes)
        extraction_method = "pdfplumber"

        if not raw_text or len(raw_text) < 50:
            raw_text = extract_text_tesseract(file_bytes, filename)
            extraction_method = "tesseract"

        if not raw_text:
            print(f"OCR extraction produced no text — filename={filename}, customer_id={customer_id}")
            return {
                "success": False,
                "extracted_fields": {},
                "message": (
                    "We couldn't process this document. Please ensure it's a clear "
                    "PDF or image of your property document, then try again."
                ),
            }

        fields = parse_fields_from_text(raw_text)

        if not fields.get("registration_number") or not fields.get("owner_name"):
            print(f"OCR extraction incomplete — filename={filename}, customer_id={customer_id}, fields={fields}")
            return {
                "success": False,
                "extracted_fields": fields,
                "message": (
                    "Could not extract registration number or owner name. Please "
                    "upload a clearer document or verify the document type is correct."
                ),
            }

        return {
            "success": True,
            "extracted_fields": fields,
            "extraction_method": extraction_method,
            "message": f"Fields extracted successfully via {extraction_method}",
        }

    except Exception as e:
        print(f"OCR extraction error — filename={filename}, customer_id={customer_id}, error={e}")
        return {
            "success": False,
            "extracted_fields": {},
            "message": (
                "We couldn't process this document. Please ensure it's a clear "
                "PDF or image of your property document, then try again."
            ),
        }
