"""
database/document_store.py
=============================
Property document uploads → Supabase Storage (bucket "property-documents")
+ a row in the `property_documents` table per upload.
"""

from database.supabase_client import supabase

BUCKET = "property-documents"


def upload_property_document(
    session_id: str,
    customer_id: str,
    doc_type: str,
    file_bytes: bytes,
    filename: str,
) -> dict:
    file_path = f"{customer_id}/{session_id}/{doc_type}/{filename}"

    supabase.storage.from_(BUCKET).upload(
        file_path,
        file_bytes,
        {"upsert": "true"},
    )

    supabase.table("property_documents").insert({
        "session_id": session_id,
        "customer_id": customer_id,
        "doc_type": doc_type,
        "file_name": filename,
        "file_path": file_path,
    }).execute()

    return {
        "success": True,
        "file_path": file_path,
        "doc_type": doc_type,
        "message": f"{filename} uploaded successfully.",
    }


def get_property_documents(session_id: str) -> list:
    res = (
        supabase.table("property_documents")
        .select("*")
        .eq("session_id", session_id)
        .execute()
    )
    return res.data or []
