"""PDF validation and MinIO upload for BOQ PDFs."""

import uuid

from fastapi import HTTPException, status

from app.shared.storage import upload_file


def validate_pdf_filename(filename: str) -> None:
    """Raise HTTPException if the filename is not a .pdf."""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .pdf files are supported for this endpoint",
        )


def upload_pdf_to_minio(
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    filename: str,
    file_bytes: bytes,
) -> str:
    """Upload a PDF to MinIO and return the object key."""
    file_uuid = uuid.uuid4()
    object_key = f"{tenant_id}/{project_id}/boq/{file_uuid}_{filename}"
    upload_file(
        object_key=object_key,
        data=file_bytes,
        content_type="application/pdf",
    )
    return object_key
