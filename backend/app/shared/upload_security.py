"""Upload security layer — validates and sanitizes uploaded files before storage.

Shared across all upload endpoints (spec PDFs, BOQ Excel, BOQ PDFs, BOQ images,
company settings uploads, and tenant pricing).
Each function raises HTTPException on failure so callers just call and continue.
"""

import logging
import re
import zipfile
from io import BytesIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from docx.document import Document as DocxDocument

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
    "docx": [b"PK\x03\x04"],               # ZIP archive (OOXML) — same as XLSX
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


# ---------------------------------------------------------------------------
# 6. Filename sanitization
# ---------------------------------------------------------------------------
def sanitize_filename(filename: str) -> str:
    """Sanitize an uploaded filename — strip path components and unsafe characters.

    Keeps only alphanumerics, hyphens, underscores, periods, and spaces.
    """
    # Extract just the filename (remove any path separators)
    name = filename.replace("\\", "/").split("/")[-1]
    # Keep only safe characters
    name = re.sub(r"[^a-zA-Z0-9._\- ]", "_", name)
    # Collapse multiple underscores/spaces
    name = re.sub(r"_+", "_", name)
    # Prevent hidden files or empty names
    if not name or name.startswith("."):
        name = "uploaded_file"
    # Limit length
    return name[:200]


# ---------------------------------------------------------------------------
# Company settings / letterhead security
# ---------------------------------------------------------------------------

# 7. DOCX package sanitization — strip macros, VBA, and embedded objects
# ---------------------------------------------------------------------------
def sanitize_docx_package(file_bytes: bytes) -> bytes:
    """Rebuild a DOCX ZIP archive without macros, VBA projects, or embedded objects.

    DOCX files are ZIP archives.  A .docm (macro-enabled) renamed to .docx
    still carries /word/vbaProject.bin inside.  python-docx ignores these
    entries but preserves them in the output, so they survive into any
    document generated from this template.

    This function copies every ZIP entry *except* known-dangerous ones,
    producing clean bytes that can be safely opened with Document().
    """
    safe_output = BytesIO()

    with zipfile.ZipFile(BytesIO(file_bytes), "r") as zin:
        with zipfile.ZipFile(safe_output, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                name_lower = item.filename.lower()
                # Macro / VBA project
                if name_lower in ("word/vbaproject.bin", "word/vbadata.xml"):
                    logger.info("Stripped macro file from DOCX: %s", item.filename)
                    continue
                # Embedded objects (could be executables)
                if name_lower.startswith("word/embeddings/"):
                    logger.info("Stripped embedded object from DOCX: %s", item.filename)
                    continue
                # ActiveX controls
                if name_lower.startswith("word/activex/"):
                    logger.info("Stripped ActiveX control from DOCX: %s", item.filename)
                    continue
                # Everything else is safe (text, images, styles, headers, footers)
                zout.writestr(item, zin.read(item.filename))

    return safe_output.getvalue()


# ---------------------------------------------------------------------------
# 8. DOCX external relationship stripping — removes tracking pixels / phone-home URLs
# ---------------------------------------------------------------------------
def strip_docx_external_relationships(doc: "DocxDocument") -> None:
    """Remove all external URL relationships from a python-docx Document.

    OOXML documents can reference external URLs (e.g. images hosted on a
    remote server).  When the document is opened in Word, it fetches those
    URLs — allowing silent tracking of every person who opens the file.

    This strips external relationships from the main document part and
    from every header/footer part.
    """

    def _clean_part_rels(part) -> None:
        if not hasattr(part, "rels"):
            return
        external_keys = [
            key for key, rel in part.rels.items() if rel.is_external
        ]
        for key in external_keys:
            logger.info(
                "Stripped external relationship from DOCX: rId=%s", key
            )
            del part.rels[key]

    # Main document body
    _clean_part_rels(doc.part)

    # Headers and footers (where tracking images typically hide)
    for section in doc.sections:
        for hf in (
            section.header,
            section.first_page_header,
            section.even_page_header,
            section.footer,
            section.first_page_footer,
            section.even_page_footer,
        ):
            # Only process headers/footers that have their own definition.
            # Accessing .part on a linked header would force-create an empty one.
            if not hf.is_linked_to_previous:
                _clean_part_rels(hf.part)
