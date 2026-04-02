"""Utility to combine multiple images into a single PDF using PyMuPDF."""

import fitz  # PyMuPDF


def combine_images_to_pdf(images: list[tuple[str, bytes]]) -> bytes:
    """Combine images into a single PDF, one image per page.

    Args:
        images: list of (filename, image_bytes) tuples.

    Returns:
        PDF bytes.
    """
    pdf = fitz.open()

    for _filename, img_bytes in images:
        img_doc = fitz.open(stream=img_bytes, filetype="png")
        # Convert image to single-page PDF
        pdf_bytes_single = img_doc.convert_to_pdf()
        img_doc.close()

        single_pdf = fitz.open("pdf", pdf_bytes_single)
        pdf.insert_pdf(single_pdf)
        single_pdf.close()

    result = pdf.tobytes()
    pdf.close()
    return result
