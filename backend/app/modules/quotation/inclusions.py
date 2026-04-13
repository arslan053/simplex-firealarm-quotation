"""Inclusion registry for quotation Notes & Exclusions section.

Defines all possible inclusion items and helpers to filter/build
the final list for document rendering.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InclusionItem:
    key: str
    text: str
    applies_to: list[int]
    mode: str  # "default" | "ask_user" | "auto_detect"
    auto_detect_subcategory: str | None
    group: str | None


INCLUSIONS: list[InclusionItem] = [
    # ══════════════════════════════════════════════════════════════
    # DEFAULT ITEMS — All service options (always printed, no user input)
    # ══════════════════════════════════════════════════════════════
    InclusionItem(
        key="authorized_distributor",
        text="We Rawabi & Gulf Marvel LTD Co is one of the authorized distributor for Simplex-Fire Alarm System.",
        applies_to=[1, 2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="programming_tc_included",
        text="Programming, Testing & Commissioning is included",
        applies_to=[1, 2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="civil_defence_coordination",
        text="We will be coordinating with MEP Contractor for our presence during testing of Fire Alarm System by Civil Defence Team",
        applies_to=[1, 2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="product_data_sheets",
        text="Product Data Sheets are included as part of Technical Submittal",
        applies_to=[1, 2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="shop_drawings_review",
        text="Shop Drawings to be done by MEP Contractor. We will review the shop drawings and provide stamp on it",
        applies_to=[1, 2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="cause_effect_matrix",
        text="We will be providing Cause & Effect Matrix in coordination with MEP Contractor",
        applies_to=[1, 2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="om_manual",
        text="We will be providing Operation & Maintenance Manual in the later stages of the project",
        applies_to=[1, 2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="mtc_certificates",
        text="We will be providing MTC certificates for the delivered material.",
        applies_to=[1, 2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="ul_certificates",
        text="We will be providing UL certificates as part of Technical Submittal",
        applies_to=[1, 2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="spares_excluded",
        text="Spares quantity is not included as part of this offer. Will be quoted separately if needed",
        applies_to=[1, 2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="training_included",
        text="Training will be provided to the operator - For maximum of 2 days, each day 6 hours are included",
        applies_to=[1, 2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="programming_variation",
        text="Programming will be done as per the approved cause and effect. If any changes are needed later or after handover of the project, this will be treated as variation",
        applies_to=[1, 2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),

    # ══════════════════════════════════════════════════════════════
    # CONDITIONAL ITEMS — User answers or system auto-detects
    # ══════════════════════════════════════════════════════════════
    InclusionItem(
        key="bms_integration",
        text="Bacnet Card for BMS Integration is included",
        applies_to=[1, 2, 3], mode="ask_user",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="printer",
        text="Printer is included",
        applies_to=[1, 2, 3], mode="ask_user",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="workstation",
        text="Work Station is included in the offer",
        applies_to=[1, 2, 3], mode="auto_detect",
        auto_detect_subcategory="work_station", group=None,
    ),
    InclusionItem(
        key="smoke_management",
        text="Smoke Management System is included on the offer for floor wise activation of Dampers or Group wise activation of FANS",
        applies_to=[1, 2, 3], mode="ask_user",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="network_existing",
        text="Network connection to Existing System is included",
        applies_to=[1, 2, 3], mode="ask_user",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="third_party_interfaces",
        text="Interfaces with 3rd Party Systems are included",
        applies_to=[1, 2, 3], mode="ask_user",
        auto_detect_subcategory=None, group=None,
    ),

    # ── Warranty (mutually exclusive — pick one) ──
    InclusionItem(
        key="warranty_12",
        text="Warranty: 12 Months from Date of supply",
        applies_to=[1, 2, 3], mode="ask_user",
        auto_detect_subcategory=None, group="warranty",
    ),
    InclusionItem(
        key="warranty_24",
        text="Warranty: 24 Months from Date of supply",
        applies_to=[1, 2, 3], mode="ask_user",
        auto_detect_subcategory=None, group="warranty",
    ),
    InclusionItem(
        key="warranty_36",
        text="Warranty: 36 Months from Date of Supply",
        applies_to=[1, 2, 3], mode="ask_user",
        auto_detect_subcategory=None, group="warranty",
    ),

    # ══════════════════════════════════════════════════════════════
    # OPTION 2/3 EXTRAS — Installation-specific defaults
    # ══════════════════════════════════════════════════════════════
    InclusionItem(
        key="cable_supply",
        text="Supply of Cables with B3 or Belden or Equivalent are Considered",
        applies_to=[2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="terminations",
        text="Terminations in our devices will be done by us and 3rd party side terminations will be done by 3rd party with coordination",
        applies_to=[2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="civil_works_excluded",
        text="Civil related works are excluded. If the delay is because of RGM in supply of material or installation or lack of sufficient manpower then we will coordinate through AFET.",
        applies_to=[2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="electrical_power",
        text="All Electrical Power needed for to be provided by Main contractor.",
        applies_to=[2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="material_availability",
        text="Material shall be readily available from RGM and work shall not be stopped by not providing access or any other delay.",
        applies_to=[2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="work_stoppage_charges",
        text="If work is stopped because of non-availability of access to work for 3 times in a row, labour hourly charges shall be charged extra to Main Contractor.",
        applies_to=[2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="installation_payment",
        text="Installation Payment \u2013 As per progress of site \u2013 calculated on per point basis \u2013 payable with current dated cheque immediately after submission of invoice.",
        applies_to=[2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="payment_delay_right",
        text="We reserve the right to stop the work if payment is delayed by more than 10 days\u2019 time",
        applies_to=[2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="daily_work_check",
        text="Work completed shall be checked on daily basis and if anything found not as per approved drawings, we shall be informed immediately. Changes will be done free of cost if our worker did not follow drawings. If any changes pointed out afterwards, it will be charged extra",
        applies_to=[2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="scaffolding_mep",
        text="Scaffolding / man Lift in High Ceiling areas to be provided by MEP Contractor",
        applies_to=[2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
]


def get_inclusions_for_option(service_option: int) -> list[InclusionItem]:
    """Return all inclusion items applicable to the given service option, in registry order."""
    return [item for item in INCLUSIONS if service_option in item.applies_to]


def get_questions_for_option(service_option: int) -> list[InclusionItem]:
    """Return only the items that need user input or show auto-detected status.
    Excludes 'default' items (they don't need any decision)."""
    return [
        item for item in INCLUSIONS
        if service_option in item.applies_to and item.mode != "default"
    ]


def build_document_items(service_option: int, inclusion_answers: dict) -> list[str]:
    """Build the final ordered list of text strings to render in the document.
    - Default items: always included
    - ask_user / auto_detect items: only if key is True in inclusion_answers
    """
    items = []
    for inc in INCLUSIONS:
        if service_option not in inc.applies_to:
            continue
        if inc.mode == "default":
            items.append(inc.text)
        elif inclusion_answers.get(inc.key) is True:
            items.append(inc.text)
    return items
