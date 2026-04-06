"""Quotation DOCX generator.

Builds a professional quotation document matching the company template.
All dimensions, fonts, and styles are derived from the reference template.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn, nsdecls
from docx.shared import Cm, Emu, Pt, RGBColor
from docx.table import _Cell

_CONTENT_WIDTH = Cm(21.00) - Cm(1.91) - Cm(2.11)  # page minus margins

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_IMAGES_DIR = _TEMPLATES_DIR / "images"

# Fonts from template analysis
_FONT_NAME = "Verdana"
_FONT_SIZE = Pt(10)
_FONT_COLOR = RGBColor(0, 0, 0)

# Page setup from template analysis
_PAGE_WIDTH = Cm(21.00)
_PAGE_HEIGHT = Cm(29.70)
_TOP_MARGIN = Cm(3.82)
_BOTTOM_MARGIN = Cm(2.38)
_LEFT_MARGIN = Cm(1.91)
_RIGHT_MARGIN = Cm(2.11)
_HEADER_DISTANCE = Cm(0.96)
_FOOTER_DISTANCE = Cm(2.03)

# Table column widths from template analysis
_COL_MODEL = Cm(3.03)
_COL_DESC = Cm(7.37)
_COL_QTY = Cm(1.73)
_COL_UNIT = Cm(2.80)
_COL_TOTAL = Cm(3.81)


@dataclass
class QuotationProduct:
    code: str
    description: str
    quantity: int | float
    unit_price: float
    total_price: float


@dataclass
class QuotationData:
    client_name: str
    client_address: str
    reference_number: str
    generation_date: date
    project_name: str
    service_option: int  # 1, 2, or 3
    products: list[QuotationProduct]
    subtotal: float
    vat: float
    grand_total: float
    payment_terms_text: str | None = None


def generate_quotation(data: QuotationData) -> bytes:
    """Generate a quotation DOCX and return it as bytes."""
    doc = Document()

    _setup_page(doc)
    _setup_header(doc)
    _setup_footer(doc)

    # Build body content
    _add_client_and_date(doc, data)
    _add_empty_para(doc)
    _add_subject(doc, data.project_name)
    _add_empty_para(doc)
    _add_greeting(doc, data.client_name)
    _add_empty_para(doc)
    _add_intro(doc)
    _add_empty_para(doc)
    _add_scope(doc, data.service_option)
    _add_empty_para(doc)
    _add_exclusions(doc, data.service_option)
    _add_empty_para(doc)
    _add_warranty(doc)
    _add_cancellation(doc)
    _add_limitation_of_liability(doc)
    _add_prices_and_terms(doc)
    _add_payment_terms(doc, data)
    _add_empty_para(doc)
    _add_time_for_supplies(doc)
    _add_empty_para(doc)
    _add_validity_and_signature(doc)
    _add_product_table(doc, data)

    # Write to bytes
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

def _setup_page(doc: Document) -> None:
    section = doc.sections[0]
    section.orientation = WD_ORIENT.PORTRAIT
    section.page_width = _PAGE_WIDTH
    section.page_height = _PAGE_HEIGHT
    section.top_margin = _TOP_MARGIN
    section.bottom_margin = _BOTTOM_MARGIN
    section.left_margin = _LEFT_MARGIN
    section.right_margin = _RIGHT_MARGIN
    section.header_distance = _HEADER_DISTANCE
    section.footer_distance = _FOOTER_DISTANCE


def _setup_header(doc: Document) -> None:
    section = doc.sections[0]
    header = section.header
    header.is_linked_to_previous = False

    # Header table: logo left, header text right — full content width
    tbl = header.add_table(rows=1, cols=2, width=_CONTENT_WIDTH)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    _remove_table_borders(tbl)

    # Logo cell
    cell_logo = tbl.cell(0, 0)
    cell_logo.width = Cm(3.5)
    p_logo = cell_logo.paragraphs[0]
    p_logo.alignment = WD_ALIGN_PARAGRAPH.LEFT
    logo_path = str(_IMAGES_DIR / "logo.png")
    p_logo.add_run().add_picture(logo_path, width=Cm(3.0))

    # Header text cell — fill remaining width
    cell_text = tbl.cell(0, 1)
    p_text = cell_text.paragraphs[0]
    p_text.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    header_text_path = str(_IMAGES_DIR / "header_text.png")
    p_text.add_run().add_picture(header_text_path, width=Cm(13.5))


def _setup_footer(doc: Document) -> None:
    section = doc.sections[0]
    footer = section.footer
    footer.is_linked_to_previous = False

    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_path = str(_IMAGES_DIR / "footer.png")
    run = p.add_run()
    run.add_picture(footer_path, width=_CONTENT_WIDTH)


# ---------------------------------------------------------------------------
# Body content builders
# ---------------------------------------------------------------------------

def _add_client_and_date(doc: Document, data: QuotationData) -> None:
    # Use a table for left/right alignment
    tbl = doc.add_table(rows=3, cols=2)
    _remove_table_borders(tbl)

    d = data.generation_date
    day_suffix = _ordinal_suffix(d.day)
    ref_str = f"Ref.: MI/203-C/{data.reference_number}"

    # Row 0: client name | date (with superscript ordinal suffix)
    _set_cell_text(tbl.cell(0, 0), f"Engr, {data.client_name}", bold=True)
    _set_date_cell(tbl.cell(0, 1), d.day, day_suffix, d.strftime('%b'), d.year)

    # Row 1: address | ref
    _set_cell_text(tbl.cell(1, 0), f"{data.client_address},")
    _set_cell_text(tbl.cell(1, 1), ref_str, bold=True, align=WD_ALIGN_PARAGRAPH.RIGHT)

    # Row 2: country
    _set_cell_text(tbl.cell(2, 0), "Saudi Arabia.")


def _add_subject(doc: Document, project_name: str) -> None:
    p = doc.add_paragraph()
    run = p.add_run(f"Subject: Fire Alarm System \u2013 Simplex- {project_name}")
    _style_run(run)


def _add_greeting(doc: Document, client_name: str) -> None:
    p = doc.add_paragraph()
    run = p.add_run(f"Dear Engr, {client_name}")
    _style_run(run)


def _add_intro(doc: Document) -> None:
    _add_body_text(doc,
        "As requested, please find herewith attached our offer for Fire Alarm System."
    )


def _add_scope(doc: Document, option: int) -> None:
    p = doc.add_paragraph()
    run = p.add_run("SCOPE")
    _style_run(run, bold=True, underline=True)

    if option == 1:
        _add_body_text(doc,
            "Price includes Supply of equipment mentioned in attached point-schedule, "
            "warranty, programming, testing & commissioning."
        )
    elif option == 2:
        _add_body_text(doc,
            "Price includes Supply of equipment mentioned in attached point-schedule, "
            "engineering support which includes preparation of Single Line diagrams, "
            "Installation of devices we supplied, conduiting, cable pulling, device fixing, "
            "programming, testing and commissioning of equipment we supplied, Client Staff "
            "training, O&M Manuals and Warranty support."
        )
    else:  # option 3
        _add_body_text(doc,
            "Price includes Supply of equipment mentioned in attached point-schedule, "
            "engineering support which includes preparation of Single Line diagrams, "
            "Installation of devices we supplied, cable pulling, device fixing, "
            "programming, testing and commissioning of equipment we supplied, Client Staff "
            "training, O&M Manuals and Warranty support."
        )


def _add_exclusions(doc: Document, option: int) -> None:
    p = doc.add_paragraph()
    run = p.add_run("EXCLUSIONS")
    _style_run(run, bold=True, underline=True)

    _add_body_text(doc, "Following are excluded from our scope and price: -")

    # Build exclusion items based on option
    all_exclusions = [
        "Any kind of civil works",
        "Any Kind of Installations or programming",
        "Any kind of cables supply and wiring together with allied works such as cable trays, trunking conduiting at field end in panels.",
        "Any kind of starters panels, MCC panels.",
        "Fittings & fixtures for peripherals, Actuators.",
        "Any other item not specifically mentioned by us in this offer.",
        "Any cost towards operating the system such as towards an operator for client, etc.",
    ]

    if option == 2:
        # Remove items 2 and 3 (installations + cables/conduiting included)
        exclusions = [all_exclusions[i] for i in (0, 3, 4, 5, 6)]
    elif option == 3:
        # Remove item 2 only (installations included, conduiting still excluded)
        exclusions = [all_exclusions[i] for i in (0, 2, 3, 4, 5, 6)]
    else:
        exclusions = all_exclusions

    for i, item in enumerate(exclusions, 1):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = p.add_run(f"{i}. {item}")
        _style_run(run)


def _add_warranty(doc: Document) -> None:
    p = doc.add_paragraph()
    run = p.add_run("WARRANTY:")
    _style_run(run, bold=True, underline=True)

    _add_body_text(doc,
        "Items supplied by us shall be covered under our standard warranty clause that "
        "covers against any material defect or malfunctioning, for a period of 18 months "
        "from date of delivery. Product shall be used as intended. Misuse or wrong application "
        "will not be covered under warranty. We also hope that project maintenance will be "
        "given to us as a separate contract so that we can maintain the system in a proper way."
    )
    _add_empty_para(doc)
    _add_body_text(doc,
        "However our warranty coverage shall not include wear & tear, consumables, "
        "abuse/ misuse/ wrong use of components"
    )


def _add_cancellation(doc: Document) -> None:
    p = doc.add_paragraph()
    run = p.add_run("CANCELLATION:")
    _style_run(run, bold=True, underline=True)

    _add_body_text(doc,
        "In case of cancellation of order for whatsoever reasons RGM reserves the right "
        "to charge the purchaser for the cost of such cancellations in accordance with "
        "the actual stage of processing."
    )


def _add_limitation_of_liability(doc: Document) -> None:
    p = doc.add_paragraph()
    run = p.add_run("LIMITATION OF LIABILITY:")
    _style_run(run, bold=True, underline=True)

    _add_body_text(doc,
        "The supplier shall not be liable, whether in contract, warranty, failure of remedy "
        "to achieve its essential purpose, tort (including negligence or strict liability) "
        "indemnity, or any other legal or equitable theory for damage to or loss of other "
        "property or equipment, business interruption or lost revenue, profits or sales, "
        "cost of capital, or for any special, incidental, punitive, indirect or consequential "
        "damages or for any other loss, costs or expenses of similar type."
    )
    _add_empty_para(doc)
    _add_body_text(doc,
        "The liability of the supplier for any act or omission, product sold, serviced or "
        "furnished directly or indirectly under this agreement, whether in contract, warranty "
        "failure or a remedy to achieve its essential purpose, tort (including negligence or "
        "strict liability) indemnity, or any other legal or equitable theory, will in no event "
        "exceed 1% of the contract value."
    )
    _add_empty_para(doc)
    _add_body_text(doc,
        "The rights and remedies contained in this agreement are exclusive, and the parties "
        "accept these remedies in lieu of all other rights and remedies available at law or "
        "otherwise, in contract (including warranty) or in tort (including negligence), for "
        "any and all claims of any nature arising under this agreement or any performance or "
        "breach arising out of this agreement."
    )


def _add_prices_and_terms(doc: Document) -> None:
    p = doc.add_paragraph()
    run = p.add_run("PRICES AND TERMS OF PAYMENT:")
    _style_run(run, bold=True, underline=True)

    _add_body_text(doc,
        "Without prejudice to any further rights, we may suspend and/ or refuse any supplies "
        "for as long as any due payment remains outstanding for whatsoever reason."
    )
    _add_empty_para(doc)
    _add_body_text(doc,
        "Late payments due and payable to supplier shall attract interest at a rated of 12% "
        "per annum accruing from their due date until full settlement of the principal amount. "
        "Payments by the purchaser shall be deemed to be made first against any accrued interest "
        "and then against the outstanding principal amount. The provision of this clause is "
        "without prejudice to any further rights of the supplier in case of payment is delayed "
        "by the purchaser."
    )


def _add_payment_terms(doc: Document, data: QuotationData) -> None:
    _add_empty_para(doc)
    p = doc.add_paragraph()
    run = p.add_run("Payment terms :")
    _style_run(run, bold=True)

    if data.payment_terms_text:
        for line in data.payment_terms_text.splitlines():
            if line.strip():
                p = doc.add_paragraph()
                run = p.add_run(line)
                _style_run(run)


def _add_time_for_supplies(doc: Document) -> None:
    p = doc.add_paragraph()
    run = p.add_run("TIME FOR SUPPLIES; DELAY:")
    _style_run(run, bold=True, underline=True)

    _add_body_text(doc,
        "Delivery \u201310 to 15 DAYS from the date of advance payment with purchase "
        "order for peripherals"
    )
    _add_body_text(doc, "4-6 weeks for panels")


def _add_validity_and_signature(doc: Document) -> None:
    p = doc.add_paragraph()
    run = p.add_run("Validity of Offer \u2013 10 days")
    _style_run(run, bold=True)

    _add_empty_para(doc)
    _add_body_text(doc, "Best regards,")

    # Signature image
    p = doc.add_paragraph()
    sig_path = str(_IMAGES_DIR / "signature.png")
    p.add_run().add_picture(sig_path, width=Cm(3.5))

    _add_body_text(doc, "Mohammed Masood Ali")
    _add_body_text(doc, "+966 55 267 3835")


def _add_product_table(doc: Document, data: QuotationData) -> None:
    # Start product table on a new page
    p = doc.add_paragraph()
    run = p.add_run()
    run.add_break(WD_BREAK.PAGE)

    num_rows = len(data.products) + 4  # header + products + total + vat + grand total
    table = doc.add_table(rows=num_rows, cols=5)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"

    # Set column widths
    for row in table.rows:
        row.cells[0].width = _COL_MODEL
        row.cells[1].width = _COL_DESC
        row.cells[2].width = _COL_QTY
        row.cells[3].width = _COL_UNIT
        row.cells[4].width = _COL_TOTAL

    # Header row
    headers = ["Model", "Description", "Qty", " Unit\nPrice ", " Total\nPrice "]
    for i, h in enumerate(headers):
        cell = table.cell(0, i)
        _set_table_cell(cell, h, bold=True)
        _shade_cell(cell, "D9D9D9")

    # Product rows
    for ri, prod in enumerate(data.products, 1):
        _set_table_cell(table.cell(ri, 0), prod.code)
        _set_table_cell(table.cell(ri, 1), prod.description)
        _set_table_cell(table.cell(ri, 2), _format_qty(prod.quantity),
                        align=WD_ALIGN_PARAGRAPH.CENTER)
        _set_table_cell(table.cell(ri, 3), _format_price(prod.unit_price),
                        align=WD_ALIGN_PARAGRAPH.RIGHT)
        _set_table_cell(table.cell(ri, 4), _format_price(prod.total_price),
                        align=WD_ALIGN_PARAGRAPH.RIGHT)

    # Total row
    total_row = len(data.products) + 1
    _set_table_cell(table.cell(total_row, 1), "TOTAL IN SAR", bold=True)
    _set_table_cell(table.cell(total_row, 4), _format_price(data.subtotal),
                    bold=True, align=WD_ALIGN_PARAGRAPH.RIGHT)

    # VAT row
    vat_row = total_row + 1
    _set_table_cell(table.cell(vat_row, 1), "VAT", bold=True)
    _set_table_cell(table.cell(vat_row, 4), _format_price(data.vat),
                    bold=True, align=WD_ALIGN_PARAGRAPH.RIGHT)

    # Grand total row
    gt_row = vat_row + 1
    _set_table_cell(table.cell(gt_row, 1), "GRAND TOTAL IN SAR", bold=True)
    _set_table_cell(table.cell(gt_row, 4), _format_price(data.grand_total),
                    bold=True, align=WD_ALIGN_PARAGRAPH.RIGHT)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_body_text(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    _style_run(run)


def _add_empty_para(doc: Document) -> None:
    p = doc.add_paragraph()
    run = p.add_run("")
    _style_run(run)


def _style_run(
    run,
    bold: bool = False,
    underline: bool = False,
    size=None,
) -> None:
    run.font.name = _FONT_NAME
    run.font.size = size or _FONT_SIZE
    run.font.color.rgb = _FONT_COLOR
    run.font.bold = bold
    run.font.underline = underline


def _set_date_cell(cell: _Cell, day: int, suffix: str, month: str, year: int) -> None:
    """Render 'Date: 29th Mar 2026' with superscript ordinal suffix."""
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    run1 = p.add_run(f"Date: {day}")
    _style_run(run1, bold=True)

    run_sup = p.add_run(suffix)
    _style_run(run_sup, bold=True, size=Pt(7))
    run_sup.font.superscript = True

    run2 = p.add_run(f" {month} {year}")
    _style_run(run2, bold=True)


def _set_cell_text(
    cell: _Cell,
    text: str,
    bold: bool = False,
    align=None,
) -> None:
    p = cell.paragraphs[0]
    if align:
        p.alignment = align
    run = p.add_run(text)
    _style_run(run, bold=bold)


def _set_table_cell(
    cell: _Cell,
    text: str,
    bold: bool = False,
    align=None,
) -> None:
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    p = cell.paragraphs[0]
    if align:
        p.alignment = align
    # Clear existing
    for run in p.runs:
        run.text = ""
    run = p.add_run(text)
    run.font.name = _FONT_NAME
    run.font.size = Pt(9)
    run.font.bold = bold


def _shade_cell(cell: _Cell, color: str) -> None:
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), color)
    shading.set(qn("w:val"), "clear")
    cell._tc.get_or_add_tcPr().append(shading)


def _remove_table_borders(table) -> None:
    tbl = table._tbl
    tblPr = tbl.tblPr if tbl.tblPr is not None else OxmlElement("w:tblPr")
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "none")
        element.set(qn("w:sz"), "0")
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), "auto")
        borders.append(element)
    tblPr.append(borders)


def _ordinal_suffix(day: int) -> str:
    if 11 <= day <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def _format_price(value: float) -> str:
    return f"{value:,.2f}"


def _format_qty(value: int | float) -> str:
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value)
