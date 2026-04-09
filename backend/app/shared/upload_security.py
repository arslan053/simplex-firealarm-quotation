"""Upload security layer — validates and sanitizes uploaded files before storage.

Shared across all upload endpoints (spec PDFs, BOQ Excel, BOQ PDFs, BOQ images).
Each function raises HTTPException on failure so callers just call and continue.
"""

import logging
import zipfile
from io import BytesIO

import fitz  # PyMuPDF
from fastapi import HTTPException, status
from PIL import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MAX_UPLOAD_BYTES = 40 * 1024 * 1024          # 40 MB
MAX_DECOMPRESSED_BYTES = 200 * 1024 * 1024   # 200 MB
MAX_COMPRESSION_RATIO = 100                   # compressed-to-decompressed
MAX_IMAGE_PIXELS = 50_000_000                 # 50 megapixels
PDF_RENDER_DPI = 200                          # DPI for PDF re-rendering

# Generic message for threat-related rejections (no detail leakage)
_REJECTED_MSG = "This file could not be processed. Please ensure it is a valid, unmodified document and try again."

# Magic byte signatures for each file type
_MAGIC_SIGNATURES: dict[str, list[bytes]] = {
    "pdf":  [b"%PDF-"],
    "xlsx": [b"PK\x03\x04"],               # ZIP archive (OOXML)
    "xls":  [b"\xd0\xcf\x11\xe0"],          # OLE2 compound document
    "png":  [b"\x89PNG\r\n\x1a\n"],
    "jpg":  [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "gif":  [b"GIF87a", b"GIF89a"],
    "bmp":  [b"BM"],
    "tiff": [b"II\x2a\x00", b"MM\x00\x2a"],
    "tif":  [b"II\x2a\x00", b"MM\x00\x2a"],
    "webp": [b"RIFF"],
}


# ---------------------------------------------------------------------------
# 1. File size validation
# ---------------------------------------------------------------------------
def validate_file_size(file_bytes: bytes, max_bytes: int = MAX_UPLOAD_BYTES) -> None:
    """Reject files that exceed the maximum allowed size."""
    if len(file_bytes) > max_bytes:
        max_mb = max_bytes / (1024 * 1024)
        actual_mb = len(file_bytes) / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                f"File size ({actual_mb:.1f} MB) exceeds the maximum "
                f"allowed size of {max_mb:.0f} MB."
            ),
        )


# ---------------------------------------------------------------------------
# 2. Magic byte validation
# ---------------------------------------------------------------------------
def validate_magic_bytes(file_bytes: bytes, expected_type: str) -> None:
    """Verify the file's binary signature matches the claimed type."""
    signatures = _MAGIC_SIGNATURES.get(expected_type)
    if signatures is None:
        return

    if not any(file_bytes[: len(sig)] == sig for sig in signatures):
        logger.warning(
            "Magic byte mismatch: expected %s, got %r",
            expected_type, file_bytes[:8],
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_REJECTED_MSG,
        )


# ---------------------------------------------------------------------------
# 3. ZIP bomb / decompression bomb check  (XLSX files)
# ---------------------------------------------------------------------------
def check_zip_bomb(file_bytes: bytes) -> None:
    """Inspect the ZIP central directory of an XLSX to detect decompression bombs."""
    try:
        with zipfile.ZipFile(BytesIO(file_bytes)) as zf:
            total_uncompressed = sum(info.file_size for info in zf.infolist())
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_REJECTED_MSG,
        )

    compressed_size = len(file_bytes)

    if total_uncompressed > MAX_DECOMPRESSED_BYTES:
        logger.warning(
            "ZIP bomb detected: decompressed=%d bytes, compressed=%d bytes",
            total_uncompressed, compressed_size,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_REJECTED_MSG,
        )

    if compressed_size > 0 and total_uncompressed / compressed_size > MAX_COMPRESSION_RATIO:
        logger.warning(
            "Suspicious compression ratio: %d:1 (decompressed=%d, compressed=%d)",
            total_uncompressed // compressed_size, total_uncompressed, compressed_size,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_REJECTED_MSG,
        )


# ---------------------------------------------------------------------------
# 4. PDF sanitization — re-render as images
# ---------------------------------------------------------------------------
def sanitize_pdf(file_bytes: bytes) -> bytes:
    """Re-render every PDF page as an image, rebuilding a clean PDF.

    Strips: JavaScript, form actions, hidden text, embedded objects,
    auto-actions, invisible content — anything non-visual.
    """
    try:
        src = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception:
        logger.warning("PDF failed to open for sanitization")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_REJECTED_MSG,
        )

    if len(src) == 0:
        src.close()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded PDF has no pages.",
        )

    try:
        dst = fitz.open()
        for page in src:
            pix = page.get_pixmap(dpi=PDF_RENDER_DPI)
            new_page = dst.new_page(
                width=page.rect.width,
                height=page.rect.height,
            )
            new_page.insert_image(new_page.rect, pixmap=pix)

        sanitized = dst.tobytes(deflate=True)
        dst.close()
        src.close()
        return sanitized
    except Exception:
        logger.exception("PDF sanitization failed")
        try:
            src.close()
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_REJECTED_MSG,
        )


# ---------------------------------------------------------------------------
# 5. Image validation — dimensions + EXIF stripping
# ---------------------------------------------------------------------------
def validate_and_clean_image(file_bytes: bytes) -> bytes:
    """Validate image dimensions and strip EXIF/metadata.

    Returns cleaned image bytes (re-saved without metadata).
    """
    try:
        img = Image.open(BytesIO(file_bytes))
    except Exception:
        logger.warning("Image failed to open for validation")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_REJECTED_MSG,
        )

    w, h = img.size
    if w * h > MAX_IMAGE_PIXELS:
        logger.warning(
            "Image dimensions too large: %dx%d = %d pixels",
            w, h, w * h,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Image dimensions ({w}x{h}) are too large. "
                f"Maximum allowed is {MAX_IMAGE_PIXELS // 1_000_000} megapixels."
            ),
        )

    # Re-save without metadata (strips EXIF, GPS, etc.)
    try:
        original_format = img.format or "PNG"
        # Map format names to Pillow save format
        save_format = {
            "JPEG": "JPEG",
            "JPG": "JPEG",
            "PNG": "PNG",
            "GIF": "GIF",
            "BMP": "BMP",
            "TIFF": "TIFF",
            "WEBP": "WEBP",
        }.get(original_format.upper(), "PNG")

        clean = Image.new(img.mode, img.size)
        clean.putdata(list(img.getdata()))

        out = BytesIO()
        clean.save(out, format=save_format)
        return out.getvalue()
    except Exception:
        logger.exception("Image metadata stripping failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_REJECTED_MSG,
        )
