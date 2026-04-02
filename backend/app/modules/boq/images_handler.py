"""Image validation, reading, combining, and MinIO upload for BOQ images."""

import uuid

from fastapi import HTTPException, UploadFile, status

from app.modules.boq.image_utils import combine_images_to_pdf
from app.shared.storage import upload_file

ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif",
}


def validate_image_filenames(files: list[UploadFile]) -> None:
    """Raise HTTPException if any file is not an allowed image type."""
    for f in files:
        name = (f.filename or "").lower()
        if not any(name.endswith(ext) for ext in ALLOWED_IMAGE_EXTENSIONS):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported image format: {f.filename}. "
                f"Allowed: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}",
            )


async def read_image_files(files: list[UploadFile]) -> list[tuple[str, bytes]]:
    """Read all UploadFile objects and return (filename, bytes) tuples."""
    images: list[tuple[str, bytes]] = []
    for f in files:
        data = await f.read()
        images.append((f.filename or "image.png", data))
    return images


def build_and_upload_combined_pdf(
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    images: list[tuple[str, bytes]],
) -> tuple[str, bytes, str]:
    """Combine images into a PDF, upload to MinIO.

    Returns:
        (object_key, pdf_bytes, generated_filename)
    """
    pdf_bytes = combine_images_to_pdf(images)
    filename = f"boq_images_{uuid.uuid4().hex[:8]}.pdf"
    file_uuid = uuid.uuid4()
    object_key = f"{tenant_id}/{project_id}/boq/{file_uuid}_{filename}"
    upload_file(
        object_key=object_key,
        data=pdf_bytes,
        content_type="application/pdf",
    )
    return object_key, pdf_bytes, filename
