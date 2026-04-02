"""Panel Selection service — determine panel type, base unit + child cards."""

import json
import logging
import math
import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.boq.models import BoqItem, Document
from app.modules.projects.models import Project
from app.modules.prompt_questions.models import PromptQuestion
from app.modules.spec.models import SpecBlock
from app.shared.openai_client import get_openai_client

logger = logging.getLogger(__name__)

# ── Panel configuration dict ──
# Each panel type defines: range, base unit map, assistive card config, child card map.
# All quantities in the maps are PER PANEL.

PANEL_CONFIGS: dict[str, dict] = {
    "4007": {
        "label": "4007-ES",
        "range": (0, 250),
        "supports_mx_addressable": True,
        "base_unit_map": {
            ("MX", "non_addressable"):    [("4007-9301", 1)],
            ("MX", "addressable"):        [("4007-9401", 1)],
            ("IDNET", "non_addressable"): [("4007-9101", 1)],
            ("IDNET", "addressable"):     [("4007-9201", 1)],
        },
        "assistive_card": {
            "range": (100, 250),
            "qty_per_panel": 2,
            "map": {
                "IDNET": "4007-9803",
                "MX":    "4007-6312",
            },
        },
        "child_card_map": {
            17: [("4606-9202", 1), ("2975-9461", 1)],
            18: [("4100-7402", 1), ("4100-7403", 1), ("4100-7404", 1)],
            20: [("4007-9805", 1)],
        },
        "printer_card": [("4007-9812", 1)],
        "networking_map": {
            "wired": [("4007-9810", 1), ("4007-9813", 2)],
            "fiber": [("4007-9810", 1), ("4007-6301", 1), ("4007-6302", 1)],
            "IP":    [("4007-2504", 1)],
        },
    },
    "4010_1bay": {
        "label": "4010 (1-Bay)",
        "range": (250, 500),
        "supports_mx_addressable": False,
        "base_unit_map": {
            ("MX", "non_addressable"):    [("4010-9505", 1), ("4010-6311", 1)],
            ("IDNET", "non_addressable"): [("4010-9501", 1), ("4010-9929", 1)],
            ("IDNET", "addressable"):     [("4010-9701", 1), ("4010-9929", 1)],
        },
        "assistive_card": None,
        "child_card_map": {
            17: [("4606-9102", 1), ("2975-9206", 1)],
            18: [("4100-7402", 1), ("4100-7403", 1), ("4100-7404", 1)],
        },
        "printer_card": [("4010-9918", 1)],
        "bms_cards": [("4010-9915", 1)],
        "bms_interface_card": ("4010-9918", 1),
        "networking_map": {
            "wired": [("4010-9922", 1), ("4010-9818", 2)],
            "fiber": [("4010-9922", 1), ("4010-6301", 1), ("4010-6302", 1)],
            "IP":    [("4010-2504", 1)],
        },
    },
    "4010_2bay": {
        "label": "4010 (2-Bay)",
        "range": (500, 1000),
        "supports_mx_addressable": False,
        "base_unit_map": {
            ("MX", "non_addressable"):    [("4010-9523", 1), ("4010-6311", 2)],
            ("IDNET", "non_addressable"): [("4010-9521", 1), ("4010-9929", 2)],
            ("IDNET", "addressable"):     [("4010-9721", 1), ("4010-9929", 2)],
        },
        "assistive_card": None,
        "child_card_map": {
            17: [("4606-9102", 1), ("2975-9206", 1)],
            18: [("4100-7402", 1), ("4100-7403", 1), ("4100-7404", 1)],
        },
        "printer_card": [("4010-9918", 1)],
        "bms_cards": [("4010-9915", 1)],
        "bms_interface_card": ("4010-9918", 1),
        "networking_map": {
            "wired": [("4010-9922", 1), ("4010-9818", 2)],
            "fiber": [("4010-9922", 1), ("4010-6301", 1), ("4010-6302", 1)],
            "IP":    [("4010-2504", 1)],
        },
    },
}

# ── LLM prompt ──

SYSTEM_PROMPT = """\
You are a fire protection system panel configuration expert. Your task is to \
analyze the BOQ (Bill of Quantities) and project specification to answer \
questions about what panel features and child cards are needed.

## Instructions

For each question, analyze ALL BOQ items and the specification text to \
determine if the described feature/device is required.

Answer each question with:
- "Yes" if the BOQ or specification clearly mentions or implies the feature
- "No" if there is no indication the feature is needed

**Numeric questions (Q21, Q206):** For these questions, return the actual \
numeric count as the "answer" field (e.g. "12", "0"). Count all matching \
items from the BOQ and sum their quantities. Return "0" if none found.

**Special: Q21 (loop count):** If the BOQ or specification does not mention \
any loop count, return "null" as the answer. If multiple loop counts are \
mentioned (e.g. "2-loop" and "4-loop"), return only the LARGEST number.

If the specification text says "No specification document available" or is \
empty, rely entirely on the BOQ items to answer each question. Examine BOQ \
descriptions and quantities carefully. Set `inferred_from` to "BOQ" for all \
answers when no spec is available.

Be thorough — check BOQ item descriptions, quantities, and specification \
sections for any mention of the relevant devices or capabilities.

## Output Format

Return ONLY valid JSON (no markdown fences):
{"answers": [{"question_no": <int>, "answer": "Yes" or "No" or "<number>", "confidence": "High" or "Medium" or "Low", "supporting_notes": ["<evidence from BOQ/spec>"], "inferred_from": "BOQ" or "Spec" or "Both" or "Neither"}]}

You MUST return an answer for EVERY question provided.\
"""


def determine_panel_type(devices_per_panel: int) -> tuple[str | None, str | None]:
    """Return (panel_type_key, panel_label) based on devices per panel."""
    for key, cfg in PANEL_CONFIGS.items():
        lo, hi = cfg["range"]
        if lo <= devices_per_panel < hi:
            return key, cfg["label"]
    return None, None


def _loops_to_panel_type(loops: int) -> str:
    """Map loop count to panel type for multi-group mode."""
    if loops <= 2:
        return "4007"
    if loops <= 4:
        return "4010_1bay"
    if loops <= 6:
        return "4010_2bay"
    return "4100ES"


# ── Pure helper functions ──

def _parse_int(val: str) -> int:
    """Parse a numeric string from LLM answer, default 0."""
    try:
        return max(0, int(re.sub(r"[^\d]", "", str(val))))
    except (ValueError, TypeError):
        return 0


def _calc_power_supplies(
    protocol: str,
    notification_type: str,
    qty_loop: int,
    qty_conv_nac: int,
    qty_addr_nac: int,
    qty_phone_ctrl: int,
    qty_std_amp: int,
    qty_backup_amp: int,
) -> int:
    """Step 12: calculate total 4100-5401 power supply cards needed."""
    total = 0

    if protocol == "MX":
        # Rule 6: 1 PSU per 3 MX loop cards
        total += math.ceil(qty_loop / 3) if qty_loop else 0
        # Rule 1: conventional NACs into pool of 6
        total += math.ceil(qty_conv_nac / 6) if qty_conv_nac else 0
    else:
        # IDNET: Rule 1 — pool IDNET loops + phone controllers + conventional NACs
        pool = qty_loop + qty_phone_ctrl + qty_conv_nac
        total += math.ceil(pool / 6) if pool else 0

    # Rule 4: 1 per addressable NAC card (both protocols)
    total += qty_addr_nac

    # Rule 5: 1 per 2 standard amplifiers
    total += math.ceil(qty_std_amp / 2) if qty_std_amp else 0

    # Rule 2: 1 per 2 backup amplifiers
    total += math.ceil(qty_backup_amp / 2) if qty_backup_amp else 0

    return total


def _select_enclosures(qty_psu: int, qty_std_amp: int) -> list[tuple[str, int]]:
    """Step 17: select enclosure(s) using greedy bin-packing.

    Each enclosure holds a fixed number of bays:
      - 3-bay  (2975-9443): capacity 3
      - 2-bay  (2975-9442): capacity 2
      - 1-bay  (2975-9441): capacity 1

    Algorithm: greedy denomination — use the largest enclosure first,
    then fill the remainder with the smallest enclosure that fits.
    This minimizes total enclosure count while avoiding waste.

    Examples:
       9 → 3×3-bay
      10 → 3×3-bay + 1×1-bay
      14 → 4×3-bay + 1×2-bay
       2 → 1×2-bay
       1 → 1×1-bay
       0 → 1×1-bay (minimum: at least one enclosure)
    """
    total = qty_psu + qty_std_amp
    if total <= 0:
        return [("2975-9441", 1)]  # minimum 1 enclosure

    result: list[tuple[str, int]] = []

    qty_3bay = total // 3
    remainder = total % 3

    if qty_3bay:
        result.append(("2975-9443", qty_3bay))

    if remainder == 2:
        result.append(("2975-9442", 1))
    elif remainder == 1:
        result.append(("2975-9441", 1))

    return result


class PanelSelectionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def run(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> dict:
        """Run panel selection logic. Returns result dict."""

        # ── 1. Load protocol ──
        protocol = await self._get_protocol(tenant_id, project_id)
        if not protocol:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Protocol not determined yet. Run spec analysis first.",
            )

        # ── 2. Compute device counts ──
        total_devices = await self._count_detection_devices(tenant_id, project_id)
        notif_counts = await self._count_notification_by_subcategory(tenant_id, project_id)
        speaker_count = notif_counts["speaker_count"]
        hornflasher_count = notif_counts["hornflasher_count"]
        panel_count = await self._get_panel_count(tenant_id, project_id)
        notification_type = await self._get_notification_type(tenant_id, project_id)
        devices_per_panel = (
            total_devices // panel_count if panel_count and panel_count > 0
            else total_devices
        )

        logger.info(
            "Panel selection: total_devices=%d, speaker_count=%d, "
            "hornflasher_count=%d, panel_count=%s, devices_per_panel=%d",
            total_devices, speaker_count, hornflasher_count,
            panel_count, devices_per_panel,
        )

        # ── 3. Load BOQ + spec + ALL questions ──
        boq_items = await self._load_boq_items(tenant_id, project_id)
        spec_text = await self._load_spec_text(tenant_id, project_id)
        questions = await self._load_questions()

        # ── 4. Call LLM (single call for both categories) ──
        llm_answers = await self._call_llm(boq_items, spec_text, questions)

        # ── 5. Store LLM answers ──
        await self._store_answers(tenant_id, project_id, questions, llm_answers)

        # ── 6. Build answer map and check 4100ES entry conditions ──
        answer_map = {a["question_no"]: a["answer"] for a in llm_answers}
        q2_answer = answer_map.get(2, "No")
        q3_answer = answer_map.get(3, "No")
        has_speakers = q2_answer == "Yes" and speaker_count > 0
        has_telephone = q3_answer == "Yes"

        # Parse loop count (Q21) — null means not specified
        q21_raw = answer_map.get(21, "null")
        loop_count: int | None = None
        if q21_raw and str(q21_raw).lower() not in ("null", "none", "n/a", ""):
            loop_count = _parse_int(str(q21_raw)) or None

        entry_reasons: list[str] = []
        if devices_per_panel >= 1000:
            entry_reasons.append(
                f"{devices_per_panel} devices/panel >= 1000"
            )
        if has_speakers:
            entry_reasons.append(
                f"speakers required (Q2=Yes, {speaker_count} speaker(s) in BOQ)"
            )
        if has_telephone:
            entry_reasons.append("telephone required")
        if loop_count is not None and loop_count > 6:
            entry_reasons.append(f"loop count {loop_count} > 6")

        logger.info("Panel selection: loop_count=%s", loop_count)

        # ── 6b. Multi-panel-group detection ──
        if not has_speakers and not has_telephone:
            panel_groups = await self._detect_panel_groups(tenant_id, project_id)
            if len(panel_groups) >= 2:
                return await self._run_multi_group(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    protocol=protocol,
                    notification_type=notification_type,
                    panel_groups=panel_groups,
                    answer_map=answer_map,
                    llm_answers=llm_answers,
                    q2_answer=q2_answer,
                    q3_answer=q3_answer,
                    total_devices=total_devices,
                    hornflasher_count=hornflasher_count,
                    speaker_count=speaker_count,
                )

        # ── 7. DECISION: 4100ES or 4007/4010? ──
        if entry_reasons:
            return await self._run_4100es(
                tenant_id=tenant_id,
                project_id=project_id,
                protocol=protocol,
                notification_type=notification_type,
                total_devices=total_devices,
                speaker_count=speaker_count,
                hornflasher_count=hornflasher_count,
                devices_per_panel=devices_per_panel,
                panel_count=panel_count,
                answer_map=answer_map,
                llm_answers=llm_answers,
                entry_reasons=entry_reasons,
                q2_answer=q2_answer,
                q3_answer=q3_answer,
                loop_count=loop_count,
            )

        # ── 8. Existing 4007/4010 path ──
        panel_type, panel_label = determine_panel_type(devices_per_panel)

        # Loop count override: if loops > 2 but device range says 4007, upgrade to 4010
        if loop_count is not None and loop_count > 2 and panel_type == "4007":
            panel_type = "4010_1bay"
            panel_label = PANEL_CONFIGS["4010_1bay"]["label"]
            logger.info(
                "Panel upgrade: 4007→4010_1bay due to loop_count=%d > 2",
                loop_count,
            )

        q1_passed = panel_type is not None

        if not q1_passed:
            detail = (
                f"{devices_per_panel} devices per panel — "
                f"no supported panel type for this range (>= 1000)"
            )
            await self._store_gate_fail(tenant_id, project_id, reason=detail)
            return {
                "panel_supported": False,
                "gate_result": {
                    "q1_total_devices": total_devices,
                    "q1_devices_per_panel": devices_per_panel,
                    "q1_panel_count": panel_count,
                    "q1_passed": False,
                    "panel_type": None,
                    "panel_label": None,
                    "mx_addressable_blocked": False,
                    "q2_answer": q2_answer,
                    "q2_passed": True,
                    "q3_answer": q3_answer,
                    "q3_passed": True,
                    "loop_count": loop_count,
                },
                "products": [],
                "message": f"No supported panel: {detail}.",
            }

        # MX + Addressable check for 4010
        config = PANEL_CONFIGS[panel_type]

        if not config["supports_mx_addressable"] and protocol == "MX" and notification_type == "addressable":
            detail = (
                f"{panel_label} does not support MX protocol "
                f"with addressable notification"
            )
            await self._store_gate_fail(tenant_id, project_id, reason=detail)
            return {
                "panel_supported": False,
                "gate_result": {
                    "q1_total_devices": total_devices,
                    "q1_devices_per_panel": devices_per_panel,
                    "q1_panel_count": panel_count,
                    "q1_passed": True,
                    "panel_type": panel_type,
                    "panel_label": panel_label,
                    "mx_addressable_blocked": True,
                    "q2_answer": q2_answer,
                    "q2_passed": True,
                    "q3_answer": q3_answer,
                    "q3_passed": True,
                    "loop_count": loop_count,
                },
                "products": [],
                "message": f"Panel not supported: {detail}.",
            }

        # Q2/Q3 gates (already known to pass since no entry_reasons)
        q2_passed = q2_answer == "No"
        q3_passed = q3_answer == "No"

        gate_result = {
            "q1_total_devices": total_devices,
            "q1_devices_per_panel": devices_per_panel,
            "q1_panel_count": panel_count,
            "q1_passed": q1_passed,
            "panel_type": panel_type,
            "panel_label": panel_label,
            "mx_addressable_blocked": False,
            "q2_answer": q2_answer,
            "q2_passed": q2_passed,
            "q3_answer": q3_answer,
            "q3_passed": q3_passed,
            "loop_count": loop_count,
        }

        # Build product list (existing 4007/4010 path — unchanged)
        products = []
        num_panels = panel_count if panel_count and panel_count > 0 else 1

        # Base unit
        base_products = config["base_unit_map"].get((protocol, notification_type))
        if base_products:
            for code, qty_pp in base_products:
                products.append(await self._product(
                    code, qty_pp * num_panels, "base_unit",
                    f"{protocol} protocol with {notification_type} notification",
                ))

        # Assistive card (4007 only)
        ac_config = config["assistive_card"]
        if ac_config:
            lo, hi = ac_config["range"]
            if lo <= devices_per_panel <= hi:
                ac_code = ac_config["map"].get(protocol)
                if ac_code:
                    ac_qty = ac_config["qty_per_panel"]
                    products.append(await self._product(
                        ac_code, ac_qty * num_panels, "assistive_card",
                        f"{devices_per_panel} devices per panel "
                        f"({lo}-{hi} range), qty {ac_qty} x {num_panels} panels",
                    ))

        # Child cards from LLM answers (Q17, Q18, Q20 — remaining questions)
        child_map = config["child_card_map"]
        for qno, card_list in child_map.items():
            if answer_map.get(qno) == "Yes":
                reason = next(
                    (
                        "; ".join(a.get("supporting_notes", []))
                        for a in llm_answers
                        if a["question_no"] == qno
                    ),
                    None,
                )
                for code, qty_pp in card_list:
                    products.append(await self._product(
                        code, qty_pp * num_panels, "child_card", reason,
                        question_no=qno,
                    ))

        # Networking cards (from project.network_type instead of Q15/Q16/Q19)
        network_type = await self._get_network_type(tenant_id, project_id)
        if network_type:
            net_cards = config["networking_map"].get(network_type, [])
            for code, qty_pp in net_cards:
                products.append(await self._product(
                    code, qty_pp * num_panels, "child_card",
                    f"Networking: project network_type={network_type}",
                ))
            logger.info(
                "4007/4010 networking: network_type=%s, %d products added",
                network_type, len(net_cards),
            )

        # Printer card (Q14 answer + workstation check)
        printer_card_selected = False
        printer = answer_map.get(14, "No") == "Yes"
        if printer:
            has_workstation = await self._has_workstation(tenant_id, project_id)
            if not has_workstation:
                printer_card_selected = True
                for code, qty_pp in config["printer_card"]:
                    products.append(await self._product(
                        code, qty_pp * num_panels, "child_card",
                        "Printer required per BOQ/spec (no workstation)",
                        question_no=14,
                    ))
            else:
                logger.info(
                    "4007/4010 printer: skipped — workstation handles printing"
                )

        # BMS cards (Q204 answer — 4010 only, 4007 has no bms_cards key)
        bms = answer_map.get(204, "No") == "Yes"
        if bms and "bms_cards" in config:
            for code, qty_pp in config["bms_cards"]:
                products.append(await self._product(
                    code, qty_pp * num_panels, "child_card",
                    "BMS integration required per BOQ/spec",
                    question_no=204,
                ))
            # BMS needs serial interface — if printer card wasn't selected, add it
            if not printer_card_selected and "bms_interface_card" in config:
                code, qty = config["bms_interface_card"]
                products.append(await self._product(
                    code, qty * num_panels, "child_card",
                    "BMS requires serial interface — printer card not selected",
                    question_no=204,
                ))
            logger.info("4010 BMS: products added")

        # Store products
        await self._store_products(tenant_id, project_id, products)

        # Resolve deferred repeater panels now that panel type is known
        await self._resolve_deferred_repeaters(tenant_id, project_id, panel_type)

        return {
            "panel_supported": True,
            "gate_result": gate_result,
            "products": products,
            "message": (
                f"{panel_label} panel configuration complete. "
                f"{len(products)} products selected."
            ),
        }

    # ── 4100ES pipeline ──

    async def _run_4100es(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        protocol: str,
        notification_type: str,
        total_devices: int,
        speaker_count: int,
        hornflasher_count: int,
        devices_per_panel: int,
        panel_count: int | None,
        answer_map: dict[int, str],
        llm_answers: list[dict],
        entry_reasons: list[str],
        q2_answer: str,
        q3_answer: str,
        loop_count: int | None = None,
    ) -> dict:
        """Orchestrate the 4100ES panel selection pipeline."""
        logger.info(
            "4100ES selected — entry reasons: %s, speaker_count=%d, "
            "hornflasher_count=%d",
            entry_reasons, speaker_count, hornflasher_count,
        )

        num_panels = panel_count if panel_count and panel_count > 0 else 1

        # Parse 4100ES-specific LLM answers
        touchscreen = answer_map.get(201, "No") == "Yes"
        backup_amps = answer_map.get(202, "No") == "Yes"
        class_a = answer_map.get(203, "No") == "Yes"
        bms = answer_map.get(204, "No") == "Yes"
        phone_jack_count = _parse_int(answer_map.get(206, "0"))

        # Re-use shared answers
        has_speakers = q2_answer == "Yes" and speaker_count > 0
        has_telephone = q3_answer == "Yes"
        printer = answer_map.get(14, "No") == "Yes"

        # Networking type from project (set during device selection)
        network_type = await self._get_network_type(tenant_id, project_id)

        # Check if workstation exists in project selections
        has_workstation = await self._has_workstation(tenant_id, project_id)

        logger.info(
            "4100ES LLM flags — touchscreen=%s, backup_amps=%s, class_a=%s, "
            "bms=%s, phone_jacks=%d, printer=%s, network_type=%s, "
            "has_workstation=%s",
            touchscreen, backup_amps, class_a, bms, phone_jack_count,
            printer, network_type, has_workstation,
        )

        products = await self._build_4100es_products(
            protocol=protocol,
            notification_type=notification_type,
            total_devices=total_devices,
            hornflasher_count=hornflasher_count,
            num_panels=num_panels,
            touchscreen=touchscreen,
            backup_amps=backup_amps,
            class_a=class_a,
            bms=bms,
            speaker_count=speaker_count,
            phone_jack_count=phone_jack_count,
            has_speakers=has_speakers,
            has_telephone=has_telephone,
            printer=printer,
            network_type=network_type,
            has_workstation=has_workstation,
        )

        await self._store_products(tenant_id, project_id, products)

        # Resolve deferred repeater panels now that panel type is known
        await self._resolve_deferred_repeaters(tenant_id, project_id, "4100ES")

        gate_result = {
            "q1_total_devices": total_devices,
            "q1_devices_per_panel": devices_per_panel,
            "q1_panel_count": panel_count,
            "q1_passed": True,
            "panel_type": "4100ES",
            "panel_label": "4100ES",
            "mx_addressable_blocked": False,
            "q2_answer": q2_answer,
            "q2_passed": True,
            "q3_answer": q3_answer,
            "q3_passed": True,
            "is_4100es": True,
            "entry_reasons": entry_reasons,
            "loop_count": loop_count,
        }

        return {
            "panel_supported": True,
            "gate_result": gate_result,
            "products": products,
            "message": (
                f"4100ES panel configuration complete. "
                f"{len(products)} products selected."
            ),
        }

    async def _build_4100es_products(
        self,
        *,
        protocol: str,
        notification_type: str,
        total_devices: int,
        hornflasher_count: int,
        num_panels: int,
        touchscreen: bool,
        backup_amps: bool,
        class_a: bool,
        bms: bool,
        speaker_count: int,
        phone_jack_count: int,
        has_speakers: bool,
        has_telephone: bool,
        printer: bool,
        network_type: str | None,
        has_workstation: bool,
        nac_override_loops: int | None = None,
    ) -> list[dict]:
        """17-step cascading product builder for 4100ES."""
        products: list[dict] = []

        # ── Step 2: Master Controller ──
        if touchscreen:
            ctrl_code = "4100-9706"
            ctrl_reason = "Touchscreen/multi-line/bilingual spec"
        else:
            ctrl_code = "4100-9701"
            ctrl_reason = "Standard LCD controller (default)"
        products.append(await self._product(
            ctrl_code, 1 * num_panels, "step_2_controller", ctrl_reason,
        ))

        # ── Step 4: Detection Loop Cards ──
        if protocol == "MX":
            loop_code = "4100-6311"
            loop_per = 150
        else:
            loop_code = "4100-3109"
            loop_per = 200
        qty_loop = math.ceil(total_devices / loop_per) if total_devices else 0
        if qty_loop:
            products.append(await self._product(
                loop_code, qty_loop, "step_4_loop_card",
                f"{total_devices} devices / {loop_per} = {qty_loop} cards",
            ))

        # ── Step 5: Notification Cards (horn/flasher/strobe — NOT speakers) ──
        if notification_type == "addressable":
            nac_code = "4100-5451"
        else:
            nac_code = "4100-5450"
        if nac_override_loops is not None:
            qty_nac = math.ceil(nac_override_loops / 6)
        else:
            qty_nac = math.ceil(hornflasher_count / 45) if hornflasher_count else 0
        if qty_nac:
            products.append(await self._product(
                nac_code, qty_nac, "step_5_nac_card",
                f"{hornflasher_count} horn/flasher devices / 45 = {qty_nac} cards",
            ))

        # Separate conventional vs addressable NAC counts for PSU calc
        qty_conv_nac = qty_nac if notification_type != "addressable" else 0
        qty_addr_nac = qty_nac if notification_type == "addressable" else 0

        # ── Step 6: Audio — Speakers & Amplifiers ──
        qty_std_amp = 0
        qty_backup_amp = 0

        if has_speakers:
            # 6a: Basic Audio Module
            products.append(await self._product(
                "4100-1412", 1, "step_6a_audio_module",
                "Speakers in BOQ — basic audio module required",
            ))

            # 6b: Amplifier
            if backup_amps:
                amp_code = "4100-1327"
                amp_per = 50
                qty_backup_amp = math.ceil(speaker_count / amp_per) if speaker_count else 1
                products.append(await self._product(
                    amp_code, qty_backup_amp, "step_6b_amplifier",
                    f"Backup spec: {speaker_count} speakers / {amp_per} = {qty_backup_amp}",
                ))
            else:
                amp_code = "4100-1333"
                amp_per = 100
                qty_std_amp = math.ceil(speaker_count / amp_per) if speaker_count else 1
                products.append(await self._product(
                    amp_code, qty_std_amp, "step_6b_amplifier",
                    f"Standard: {speaker_count} speakers / {amp_per} = {qty_std_amp}",
                ))

        # ── Step 7: Telephone / FFT ──
        qty_phone_ctrl = 0

        if has_telephone:
            # 7a: Master Telephone
            products.append(await self._product(
                "4100-1270", 1, "step_7a_telephone",
                "Telephone/FFT in BOQ — master telephone required",
            ))

            # 7b: Expansion Phone Controller
            if phone_jack_count:
                qty_phone_ctrl = math.ceil(phone_jack_count / 45)
                products.append(await self._product(
                    "4100-1272", qty_phone_ctrl, "step_7b_phone_controller",
                    f"{phone_jack_count} jacks / 45 = {qty_phone_ctrl} controllers",
                ))

        # ── Step 8: Class A Wiring Adapters ──
        if class_a:
            if qty_std_amp:
                products.append(await self._product(
                    "4100-1249", qty_std_amp, "step_8_class_a",
                    f"Class A adapter for {qty_std_amp} standard amplifiers",
                ))
            if qty_backup_amp:
                products.append(await self._product(
                    "4100-1246", qty_backup_amp, "step_8_class_a",
                    f"Class A adapter for {qty_backup_amp} backup amplifiers",
                ))
            if qty_phone_ctrl:
                products.append(await self._product(
                    "4100-1273", qty_phone_ctrl, "step_8_class_a",
                    f"Class A adapter for {qty_phone_ctrl} phone controllers",
                ))

        # ── Step 9: Printer & BMS ──
        printer_card_selected = False
        if printer and not has_workstation:
            printer_card_selected = True
            products.append(await self._product(
                "4100-6038", 1, "step_9_printer",
                "Printer required per BOQ/spec (no workstation — panel needs printer card)",
            ))
        if bms:
            products.append(await self._product(
                "4100-6069", 1, "step_9_bms",
                "BMS integration required per BOQ/spec",
            ))
            if not printer_card_selected:
                products.append(await self._product(
                    "4100-6038", 1, "step_9_bms_interface",
                    "BMS requires serial interface — printer card not selected",
                ))

        # ── Step 10: 8-Switch/8-LED Module & LED Controller ──
        qty_1461 = qty_std_amp  # 1 per standard amp
        qty_1461 += math.ceil(qty_backup_amp / 2) if qty_backup_amp else 0
        qty_1461 += math.ceil(qty_phone_ctrl / 2) if qty_phone_ctrl else 0

        if qty_1461:
            products.append(await self._product(
                "4100-1461", qty_1461, "step_10_led_module",
                f"From amps ({qty_std_amp} std + ceil({qty_backup_amp}/2) backup) "
                f"+ ceil({qty_phone_ctrl}/2) phone",
            ))
            qty_1450 = math.ceil(qty_1461 / 4)
            products.append(await self._product(
                "4100-1450", qty_1450, "step_10_led_module",
                f"ceil({qty_1461} modules / 4) = {qty_1450} controllers",
            ))

        # ── Step 11: Networking (from project.network_type) ──
        # Each panel needs its own set of networking cards (× num_panels)
        if network_type == "wired":
            products.append(await self._product(
                "4100-6078", 1 * num_panels, "step_11_networking",
                f"Wired networking — NIC × {num_panels} panels",
            ))
            products.append(await self._product(
                "4100-6056", 2 * num_panels, "step_11_networking",
                f"Wired networking — media cards (2 per panel × {num_panels})",
            ))
        elif network_type == "fiber":
            products.append(await self._product(
                "4100-6078", 1 * num_panels, "step_11_networking",
                f"Fiber networking — NIC × {num_panels} panels",
            ))
            products.append(await self._product(
                "4100-6301", 1 * num_panels, "step_11_networking",
                f"Fiber networking — SM-L duplex × {num_panels} panels",
            ))
            products.append(await self._product(
                "4100-6302", 1 * num_panels, "step_11_networking",
                f"Fiber networking — SM-R duplex × {num_panels} panels",
            ))
        elif network_type == "IP":
            products.append(await self._product(
                "4100-2504", 1 * num_panels, "step_11_networking",
                f"IP networking — CS Gateway × {num_panels} panels",
            ))

        # ── Step 12: Power Supply Cards ──
        qty_psu = _calc_power_supplies(
            protocol=protocol,
            notification_type=notification_type,
            qty_loop=qty_loop,
            qty_conv_nac=qty_conv_nac,
            qty_addr_nac=qty_addr_nac,
            qty_phone_ctrl=qty_phone_ctrl,
            qty_std_amp=qty_std_amp,
            qty_backup_amp=qty_backup_amp,
        )
        if qty_psu:
            products.append(await self._product(
                "4100-5401", qty_psu, "step_12_power_supply",
                f"PSU calculation: {qty_psu} total from card load rules",
            ))

        # ── Step 13: Additional PDM Cables ──
        # 1 default (from step 3) + 1 per PSU
        total_cable = 1 + qty_psu
        products.append(await self._product(
            "4100-0646", total_cable, "step_3_13_pdm_cable",
            f"1 default + {qty_psu} per PSU = {total_cable}",
        ))

        # ── Step 14: Additional PDMs ──
        extra_pdm_psu = math.ceil(qty_psu / 3) if qty_psu else 0
        extra_pdm_amp = math.ceil(qty_std_amp / 3) if qty_std_amp else 0
        total_pdm = 1 + extra_pdm_psu + extra_pdm_amp
        products.append(await self._product(
            "4100-0635", total_pdm, "step_3_14_pdm",
            f"1 default + ceil({qty_psu}/3) PSU + ceil({qty_std_amp}/3) amp = {total_pdm}",
        ))

        # ── Step 15: Expansion Bays ──
        qty_bays = qty_psu + qty_std_amp
        if qty_bays:
            products.append(await self._product(
                "4100-2300", qty_bays, "step_15_expansion_bay",
                f"{qty_psu} PSU + {qty_std_amp} std amp = {qty_bays} bays",
            ))

        # ── Step 16: Filler Plates ──
        if qty_bays:
            qty_filler = qty_bays * 8
            products.append(await self._product(
                "4100-1279", qty_filler, "step_16_filler_plate",
                f"{qty_bays} bays x 8 = {qty_filler} fillers",
            ))

        # ── Step 17: Enclosure (greedy bin-packing) ──
        total_slots = qty_psu + qty_std_amp
        enclosures = _select_enclosures(qty_psu, qty_std_amp)
        for encl_code, encl_qty in enclosures:
            products.append(await self._product(
                encl_code, encl_qty, "step_17_enclosure",
                f"Total slots={total_slots} (PSU={qty_psu} + amp={qty_std_amp}), "
                f"greedy bin-packing",
            ))

        return products

    # ── Multi-panel-group methods ──

    async def _detect_panel_groups(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> list[dict]:
        """Detect distinct loop-count groups from panel BOQ items.

        Returns empty list if 0 or 1 distinct loop counts found.
        """
        result = await self.db.execute(text("""
            SELECT id, description, quantity
            FROM boq_items
            WHERE tenant_id = :tid
              AND project_id = :pid
              AND category = 'panel'
              AND is_hidden = false
        """), {"tid": tenant_id, "pid": project_id})
        rows = result.fetchall()

        loop_re = re.compile(r'(\d+)\s*[-–]?\s*loop', re.IGNORECASE)
        groups: list[dict] = []
        seen_loops: set[int] = set()

        for row in rows:
            desc = row.description or ""
            m = loop_re.search(desc)
            if not m:
                continue
            loops = int(m.group(1))
            if loops <= 0:
                continue
            seen_loops.add(loops)
            groups.append({
                "boq_item_id": str(row.id),
                "description": desc,
                "loop_count": loops,
                "quantity": int(row.quantity) if row.quantity else 1,
            })

        if len(seen_loops) < 2:
            return []

        logger.info(
            "Multi-group detected: %d groups with %d distinct loop counts %s",
            len(groups), len(seen_loops), sorted(seen_loops),
        )
        return groups

    async def _run_multi_group(
        self,
        *,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        protocol: str,
        notification_type: str,
        panel_groups: list[dict],
        answer_map: dict[int, str],
        llm_answers: list[dict],
        q2_answer: str,
        q3_answer: str,
        total_devices: int,
        hornflasher_count: int,
        speaker_count: int,
    ) -> dict:
        """Orchestrate multi-panel-group selection."""
        logger.info("Running multi-group panel selection for %d groups", len(panel_groups))

        # 1. Assign panel types per group
        for g in panel_groups:
            g["panel_type"] = _loops_to_panel_type(g["loop_count"])
            g["panel_label"] = (
                PANEL_CONFIGS[g["panel_type"]]["label"]
                if g["panel_type"] != "4100ES"
                else "4100ES"
            )

        # 2. Designate main panel (highest priority type, then most loops, then most qty)
        priority = {"4100ES": 4, "4010_2bay": 3, "4010_1bay": 2, "4007": 1}
        panel_groups.sort(
            key=lambda g: (priority.get(g["panel_type"], 0), g["loop_count"], g["quantity"]),
            reverse=True,
        )
        panel_groups[0]["is_main"] = True
        for g in panel_groups[1:]:
            g["is_main"] = False

        main_group = panel_groups[0]

        # 3. Store panel groups to DB
        stored_groups = await self._store_panel_groups(tenant_id, project_id, panel_groups)

        # Map groups to their generated IDs
        for g, sg in zip(panel_groups, stored_groups):
            g["id"] = sg["id"]

        # 4. Clear old panel_selections for this project
        await self.db.execute(text(
            "DELETE FROM panel_selections WHERE tenant_id = :tid AND project_id = :pid"
        ), {"tid": tenant_id, "pid": project_id})
        await self.db.flush()

        # 5. Build main panel products
        all_products: list[dict] = []
        main_type = main_group["panel_type"]
        main_qty = main_group["quantity"]

        if main_type == "4100ES":
            # Parse 4100ES-specific LLM answers
            touchscreen = answer_map.get(201, "No") == "Yes"
            backup_amps = answer_map.get(202, "No") == "Yes"
            class_a = answer_map.get(203, "No") == "Yes"
            bms = answer_map.get(204, "No") == "Yes"
            phone_jack_count = _parse_int(answer_map.get(206, "0"))
            printer = answer_map.get(14, "No") == "Yes"
            network_type = await self._get_network_type(tenant_id, project_id)
            has_workstation = await self._has_workstation(tenant_id, project_id)

            main_products = await self._build_4100es_products(
                protocol=protocol,
                notification_type=notification_type,
                total_devices=total_devices,
                hornflasher_count=hornflasher_count,
                num_panels=main_qty,
                touchscreen=touchscreen,
                backup_amps=backup_amps,
                class_a=class_a,
                bms=bms,
                speaker_count=speaker_count,
                phone_jack_count=phone_jack_count,
                has_speakers=False,
                has_telephone=False,
                printer=printer,
                network_type=network_type,
                has_workstation=has_workstation,
                nac_override_loops=main_group["loop_count"],
            )
        else:
            main_products = await self._build_4007_4010_main_products(
                panel_type=main_type,
                protocol=protocol,
                notification_type=notification_type,
                num_panels=main_qty,
                devices_per_panel=total_devices // max(main_qty, 1),
                answer_map=answer_map,
                llm_answers=llm_answers,
                tenant_id=tenant_id,
                project_id=project_id,
            )

        await self._store_products(
            tenant_id, project_id, main_products,
            panel_group_id=main_group["id"],
            skip_delete=True,
        )
        all_products.extend(main_products)

        # 6. Build non-main group products (base unit + networking)
        network_type = await self._get_network_type(tenant_id, project_id)
        for g in panel_groups:
            if g["is_main"]:
                continue

            pt = g["panel_type"]
            group_products: list[dict] = []

            if pt == "4100ES":
                # 4100ES base: controller × qty
                group_products.append(await self._product(
                    "4100-9701", g["quantity"], "base_unit",
                    f"Multi-group: {g['description']} — base unit",
                ))
                # 4100ES networking
                if network_type == "wired":
                    group_products.append(await self._product(
                        "4100-6078", 1 * g["quantity"], "step_11_networking",
                        f"Wired networking — NIC × {g['quantity']} panels",
                    ))
                    group_products.append(await self._product(
                        "4100-6056", 2 * g["quantity"], "step_11_networking",
                        f"Wired networking — media cards (2 per panel × {g['quantity']})",
                    ))
                elif network_type == "fiber":
                    group_products.append(await self._product(
                        "4100-6078", 1 * g["quantity"], "step_11_networking",
                        f"Fiber networking — NIC × {g['quantity']} panels",
                    ))
                    group_products.append(await self._product(
                        "4100-6301", 1 * g["quantity"], "step_11_networking",
                        f"Fiber networking — SM-L duplex × {g['quantity']} panels",
                    ))
                    group_products.append(await self._product(
                        "4100-6302", 1 * g["quantity"], "step_11_networking",
                        f"Fiber networking — SM-R duplex × {g['quantity']} panels",
                    ))
                elif network_type == "IP":
                    group_products.append(await self._product(
                        "4100-2504", 1 * g["quantity"], "step_11_networking",
                        f"IP networking — CS Gateway × {g['quantity']} panels",
                    ))
            else:
                config = PANEL_CONFIGS[pt]
                base_entries = config["base_unit_map"].get((protocol, notification_type))
                if not base_entries:
                    # Fallback: try non_addressable
                    base_entries = config["base_unit_map"].get((protocol, "non_addressable"), [])
                for code, qty_pp in base_entries:
                    group_products.append(await self._product(
                        code, qty_pp * g["quantity"], "base_unit",
                        f"Multi-group: {g['description']} — base unit",
                    ))
                # Networking from panel config
                if network_type:
                    net_cards = config["networking_map"].get(network_type, [])
                    for code, qty_pp in net_cards:
                        group_products.append(await self._product(
                            code, qty_pp * g["quantity"], "child_card",
                            f"Networking: network_type={network_type} × {g['quantity']} panels",
                        ))

            await self._store_products(
                tenant_id, project_id, group_products,
                panel_group_id=g["id"],
                skip_delete=True,
            )
            all_products.extend(group_products)

        # 7. Resolve deferred repeaters using main panel type
        await self._resolve_deferred_repeaters(tenant_id, project_id, main_type)

        # 8. Build result
        gate_result = {
            "q1_total_devices": total_devices,
            "q1_devices_per_panel": total_devices,
            "q1_panel_count": sum(g["quantity"] for g in panel_groups),
            "q1_passed": True,
            "panel_type": main_type,
            "panel_label": main_group["panel_label"],
            "mx_addressable_blocked": False,
            "q2_answer": q2_answer,
            "q2_passed": True,
            "q3_answer": q3_answer,
            "q3_passed": True,
            "is_4100es": main_type == "4100ES",
            "entry_reasons": [],
            "loop_count": main_group["loop_count"],
            "is_multi_group": True,
        }

        return {
            "panel_supported": True,
            "gate_result": gate_result,
            "products": all_products,
            "is_multi_group": True,
            "message": (
                f"Multi-group panel configuration complete. "
                f"{len(panel_groups)} groups, {len(all_products)} products selected."
            ),
        }

    async def _build_4007_4010_main_products(
        self,
        *,
        panel_type: str,
        protocol: str,
        notification_type: str,
        num_panels: int,
        devices_per_panel: int,
        answer_map: dict[int, str],
        llm_answers: list[dict],
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> list[dict]:
        """Build full product list for a 4007/4010 main panel in multi-group mode."""
        config = PANEL_CONFIGS[panel_type]
        products: list[dict] = []

        # Base unit
        base_products = config["base_unit_map"].get((protocol, notification_type))
        if base_products:
            for code, qty_pp in base_products:
                products.append(await self._product(
                    code, qty_pp * num_panels, "base_unit",
                    f"{protocol} protocol with {notification_type} notification",
                ))

        # Assistive card (4007 only)
        ac_config = config["assistive_card"]
        if ac_config:
            lo, hi = ac_config["range"]
            if lo <= devices_per_panel <= hi:
                ac_code = ac_config["map"].get(protocol)
                if ac_code:
                    ac_qty = ac_config["qty_per_panel"]
                    products.append(await self._product(
                        ac_code, ac_qty * num_panels, "assistive_card",
                        f"{devices_per_panel} devices per panel "
                        f"({lo}-{hi} range), qty {ac_qty} x {num_panels} panels",
                    ))

        # Child cards from LLM answers (Q17, Q18, Q20)
        child_map = config["child_card_map"]
        for qno, card_list in child_map.items():
            if answer_map.get(qno) == "Yes":
                reason = next(
                    (
                        "; ".join(a.get("supporting_notes", []))
                        for a in llm_answers
                        if a["question_no"] == qno
                    ),
                    None,
                )
                for code, qty_pp in card_list:
                    products.append(await self._product(
                        code, qty_pp * num_panels, "child_card", reason,
                        question_no=qno,
                    ))

        # Networking cards
        network_type = await self._get_network_type(tenant_id, project_id)
        if network_type:
            net_cards = config["networking_map"].get(network_type, [])
            for code, qty_pp in net_cards:
                products.append(await self._product(
                    code, qty_pp * num_panels, "child_card",
                    f"Networking: project network_type={network_type}",
                ))

        # Printer card (Q14)
        printer_card_selected = False
        printer = answer_map.get(14, "No") == "Yes"
        if printer:
            has_workstation = await self._has_workstation(tenant_id, project_id)
            if not has_workstation:
                printer_card_selected = True
                for code, qty_pp in config["printer_card"]:
                    products.append(await self._product(
                        code, qty_pp * num_panels, "child_card",
                        "Printer required per BOQ/spec (no workstation)",
                        question_no=14,
                    ))

        # BMS cards (Q204 — 4010 only)
        bms = answer_map.get(204, "No") == "Yes"
        if bms and "bms_cards" in config:
            for code, qty_pp in config["bms_cards"]:
                products.append(await self._product(
                    code, qty_pp * num_panels, "child_card",
                    "BMS integration required per BOQ/spec",
                    question_no=204,
                ))
            if not printer_card_selected and "bms_interface_card" in config:
                code, qty = config["bms_interface_card"]
                products.append(await self._product(
                    code, qty * num_panels, "child_card",
                    "BMS requires serial interface — printer card not selected",
                    question_no=204,
                ))

        return products

    async def _store_panel_groups(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        groups: list[dict],
    ) -> list[dict]:
        """Clear old panel groups and insert new ones. Returns records with IDs."""
        await self.db.execute(text(
            "DELETE FROM panel_groups WHERE tenant_id = :tid AND project_id = :pid"
        ), {"tid": tenant_id, "pid": project_id})
        await self.db.flush()

        stored: list[dict] = []
        for g in groups:
            result = await self.db.execute(text("""
                INSERT INTO panel_groups
                    (tenant_id, project_id, boq_item_id, description,
                     loop_count, quantity, panel_type, is_main)
                VALUES
                    (:tid, :pid, :bid, :desc, :loops, :qty, :ptype, :is_main)
                RETURNING id
            """), {
                "tid": tenant_id,
                "pid": project_id,
                "bid": g.get("boq_item_id"),
                "desc": g.get("description"),
                "loops": g["loop_count"],
                "qty": g["quantity"],
                "ptype": g["panel_type"],
                "is_main": g.get("is_main", False),
            })
            row = result.first()
            stored.append({"id": str(row.id), **g})
        await self.db.flush()
        return stored

    # ── Deferred repeater resolution ──

    _PANEL_HINT_MAP: dict[str, str] = {
        "4100ES": "4100es",
        "4007": "4007es",
        "4010_1bay": "4010es",
        "4010_2bay": "4010es",
    }

    async def _resolve_deferred_repeaters(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        panel_type: str,
    ) -> None:
        """Auto-resolve repeater panels deferred during device selection."""
        keyword = self._PANEL_HINT_MAP.get(panel_type)
        if not keyword:
            logger.warning("No repeater hint mapping for panel_type=%s", panel_type)
            return

        # Find the matching repeater selectable
        sel_result = await self.db.execute(text("""
            SELECT s.id,
                   COALESCE(
                       array_agg(DISTINCT p.code) FILTER (WHERE p.code IS NOT NULL),
                       '{}'
                   ) AS product_codes
            FROM selectables s
            LEFT JOIN selectable_products sp ON sp.selectable_id = s.id
            LEFT JOIN products p ON p.id = sp.product_id
            WHERE s.description = 'Repeator Panel'
              AND s.category = 'annunciator_subpanel'
              AND LOWER(s.specification_hints) LIKE :hint
            GROUP BY s.id
            LIMIT 1
        """), {"hint": f"%{keyword}%"})
        row = sel_result.first()

        if not row:
            logger.warning(
                "No repeater selectable found for keyword=%s — "
                "deferred repeaters will stay pending",
                keyword,
            )
            return

        sel_id = str(row.id)
        p_codes = list(row.product_codes) if row.product_codes else []

        result = await self.db.execute(text("""
            UPDATE boq_device_selections
            SET selectable_id = :sel_id,
                status = 'finalized',
                deferred_type = NULL,
                product_codes = :codes,
                reason = :reason
            WHERE tenant_id = :tid
              AND project_id = :pid
              AND status = 'pending_panel'
              AND deferred_type = 'repeater_panel'
        """), {
            "sel_id": sel_id,
            "codes": p_codes,
            "reason": f"Resolved: repeater panel for {panel_type} series",
            "tid": tenant_id,
            "pid": project_id,
        })
        resolved = result.rowcount
        if resolved:
            logger.info(
                "Resolved %d deferred repeater panel(s) → selectable %s (%s)",
                resolved, sel_id, panel_type,
            )
            await self.db.flush()

    # ── Private helpers ──

    async def _product(
        self,
        code: str,
        qty: int,
        source: str,
        reason: str | None,
        *,
        question_no: int | None = None,
    ) -> dict:
        """Build a product dict with name lookup."""
        name = await self._get_product_name(code)
        return {
            "product_code": code,
            "product_name": name,
            "quantity": qty,
            "source": source,
            "question_no": question_no,
            "reason": reason,
        }

    async def _get_protocol(
        self, tenant_id: uuid.UUID, project_id: uuid.UUID,
    ) -> str | None:
        """Read protocol directly from projects table."""
        result = await self.db.execute(
            select(Project.protocol).where(
                Project.id == project_id,
                Project.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def _get_network_type(
        self, tenant_id: uuid.UUID, project_id: uuid.UUID,
    ) -> str | None:
        """Read network_type from projects table (set during device selection)."""
        result = await self.db.execute(
            select(Project.network_type).where(
                Project.id == project_id,
                Project.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def _has_workstation(
        self, tenant_id: uuid.UUID, project_id: uuid.UUID,
    ) -> bool:
        """Check if any BOQ item is matched to a work_station selectable."""
        result = await self.db.execute(text("""
            SELECT 1
            FROM boq_device_selections ds
            JOIN selectables s ON s.id = ds.selectable_id
            WHERE ds.tenant_id = :tid
              AND ds.project_id = :pid
              AND s.subcategory = 'work_station'
            LIMIT 1
        """), {"tid": tenant_id, "pid": project_id})
        return result.first() is not None

    async def _get_panel_count(
        self, tenant_id: uuid.UUID, project_id: uuid.UUID,
    ) -> int | None:
        """Get panel count from panel analysis answers (Q101/Q102 multi-panel)."""
        result = await self.db.execute(text("""
            SELECT pq.question_no, aa.answer
            FROM analysis_answers aa
            JOIN prompt_questions pq ON pq.id = aa.question_id
            WHERE aa.tenant_id = :tid
              AND aa.project_id = :pid
              AND pq.category = 'Panel_selection'
              AND pq.question_no IN (101, 102, 103)
        """), {"tid": tenant_id, "pid": project_id})
        rows = result.fetchall()
        if not rows:
            return None

        answers = {row.question_no: row.answer for row in rows}

        if answers.get(101) == "Yes" or answers.get(102) == "Yes":
            count_result = await self.db.execute(text("""
                SELECT COALESCE(SUM(quantity), 0)
                FROM boq_items
                WHERE tenant_id = :tid
                  AND project_id = :pid
                  AND category = 'panel'
                  AND is_hidden = false
            """), {"tid": tenant_id, "pid": project_id})
            panel_count = int(count_result.scalar_one())
            return panel_count if panel_count > 0 else None

        return None

    async def _count_detection_devices(
        self, tenant_id: uuid.UUID, project_id: uuid.UUID,
    ) -> int:
        """Sum BOQ item quantities where matched selectable is a detection device."""
        result = await self.db.execute(text("""
            SELECT COALESCE(SUM(bi.quantity), 0) AS total
            FROM boq_device_selections ds
            JOIN boq_items bi ON bi.id = ds.boq_item_id
            JOIN selectables s ON s.id = ds.selectable_id
            WHERE ds.tenant_id = :tid
              AND ds.project_id = :pid
              AND s.category IN ('mx_detection_device', 'idnet_detection_device')
        """), {"tid": tenant_id, "pid": project_id})
        return result.scalar_one()

    async def _count_notification_by_subcategory(
        self, tenant_id: uuid.UUID, project_id: uuid.UUID,
    ) -> dict[str, int]:
        """Count notification devices by subcategory from BOQ selections.

        Returns dict with:
          speaker_count: speakers + speaker_flashers (for amplifier calc)
          hornflasher_count: all non-speaker notification (for NAC card calc)
        """
        result = await self.db.execute(text("""
            SELECT
                COALESCE(SUM(bi.quantity) FILTER (
                    WHERE s.subcategory IN ('speaker', 'speaker_flasher')
                ), 0) AS speaker_count,
                COALESCE(SUM(bi.quantity) FILTER (
                    WHERE s.subcategory IN (
                        'speaker_flasher', 'horn', 'horn_flasher',
                        'strobe', 'flasher', 'strobe_flasher'
                    )
                ), 0) AS hornflasher_count
            FROM boq_device_selections ds
            JOIN boq_items bi ON bi.id = ds.boq_item_id
            JOIN selectables s ON s.id = ds.selectable_id
            WHERE ds.tenant_id = :tid
              AND ds.project_id = :pid
              AND s.subcategory IS NOT NULL
        """), {"tid": tenant_id, "pid": project_id})
        row = result.first()
        return {
            "speaker_count": int(row.speaker_count) if row else 0,
            "hornflasher_count": int(row.hornflasher_count) if row else 0,
        }

    async def _get_notification_type(
        self, tenant_id: uuid.UUID, project_id: uuid.UUID,
    ) -> str:
        """Determine notification type from device selection results."""
        result = await self.db.execute(text("""
            SELECT DISTINCT s.category
            FROM boq_device_selections ds
            JOIN selectables s ON s.id = ds.selectable_id
            WHERE ds.tenant_id = :tid
              AND ds.project_id = :pid
              AND s.category IN (
                  'addressable_notification_device',
                  'non_addressable_notification_device'
              )
        """), {"tid": tenant_id, "pid": project_id})
        categories = [row[0] for row in result.fetchall()]

        if "non_addressable_notification_device" in categories:
            return "non_addressable"
        if "addressable_notification_device" in categories:
            return "addressable"
        return "non_addressable"  # default

    async def _load_boq_items(
        self, tenant_id: uuid.UUID, project_id: uuid.UUID,
    ) -> list[dict]:
        result = await self.db.execute(
            select(BoqItem)
            .where(
                BoqItem.tenant_id == tenant_id,
                BoqItem.project_id == project_id,
                BoqItem.type == "boq_item",
            )
            .order_by(BoqItem.row_number.asc())
        )
        items = result.scalars().all()
        return [
            {
                "id": str(item.id),
                "description": item.description,
                "quantity": int(item.quantity) if item.quantity else 0,
            }
            for item in items
        ]

    async def _load_spec_text(
        self, tenant_id: uuid.UUID, project_id: uuid.UUID,
    ) -> str | None:
        spec_doc_result = await self.db.execute(
            select(Document).where(
                and_(
                    Document.tenant_id == tenant_id,
                    Document.project_id == project_id,
                    Document.type == "SPEC",
                )
            )
        )
        spec_doc = spec_doc_result.scalar_one_or_none()
        if not spec_doc:
            return None

        blocks_result = await self.db.execute(
            select(SpecBlock.content)
            .where(
                SpecBlock.document_id == spec_doc.id,
                SpecBlock.tenant_id == tenant_id,
            )
            .order_by(SpecBlock.page_no.asc(), SpecBlock.order_in_page.asc())
        )
        blocks = blocks_result.scalars().all()
        if not blocks:
            return None
        return "\n".join(blocks)

    async def _load_questions(self) -> list[dict]:
        result = await self.db.execute(
            select(PromptQuestion)
            .where(PromptQuestion.category.in_([
                "4007_panel_questions",
                "4100ES_panel_questions",
            ]))
            .order_by(PromptQuestion.question_no.asc())
        )
        rows = result.scalars().all()
        if not rows:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Panel questions not seeded. Run seed script.",
            )
        return [
            {"id": str(q.id), "question_no": q.question_no, "question": q.question}
            for q in rows
        ]

    async def _call_llm(
        self,
        boq_items: list[dict],
        spec_text: str | None,
        questions: list[dict],
    ) -> list[dict]:
        boq_json = json.dumps(boq_items, ensure_ascii=False)
        questions_text = "\n".join(
            f"Q{q['question_no']}: {q['question']}" for q in questions
        )

        parts = [
            "== BOQ Items ==\n",
            boq_json,
            "\n\n== Project Specification ==\n",
            spec_text or "No specification document available.",
            "\n\n== Questions ==\n",
            questions_text,
        ]
        user_msg = "".join(parts)

        logger.info("Panel selection: calling LLM for %d questions", len(questions))

        client = get_openai_client()
        response = await client.responses.create(
            model="gpt-5.2",
            instructions=SYSTEM_PROMPT,
            input=[{"role": "user", "content": user_msg}],
        )

        raw_text = _extract_text(response)
        parsed = _parse_json(raw_text)

        if not isinstance(parsed, dict) or "answers" not in parsed:
            logger.error("Unexpected LLM response format: %s", raw_text[:500])
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI returned an invalid response. Please try again.",
            )

        return parsed["answers"]

    async def _store_answers(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        questions: list[dict],
        llm_answers: list[dict],
    ) -> None:
        """Store LLM answers in analysis_answers table."""
        q_lookup = {q["question_no"]: q["id"] for q in questions}

        q_ids = [q["id"] for q in questions]
        if q_ids:
            await self.db.execute(text("""
                DELETE FROM analysis_answers
                WHERE tenant_id = :tid
                  AND project_id = :pid
                  AND question_id = ANY(:qids)
            """), {"tid": tenant_id, "pid": project_id, "qids": q_ids})
            await self.db.flush()

        for ans in llm_answers:
            qno = ans.get("question_no")
            qid = q_lookup.get(qno)
            if not qid:
                logger.warning("LLM returned unknown question_no %s — skipping", qno)
                continue

            notes = ans.get("supporting_notes", [])
            if isinstance(notes, list):
                notes_json = json.dumps(notes)
            else:
                notes_json = json.dumps([str(notes)])

            await self.db.execute(text("""
                INSERT INTO analysis_answers
                    (tenant_id, project_id, question_id, answer, confidence,
                     supporting_notes, inferred_from)
                VALUES
                    (:tid, :pid, :qid, :answer, :confidence, :notes, :inferred)
            """), {
                "tid": tenant_id,
                "pid": project_id,
                "qid": qid,
                "answer": ans.get("answer", "No"),
                "confidence": ans.get("confidence", "Low"),
                "notes": notes_json,
                "inferred": ans.get("inferred_from", "Neither"),
            })
        await self.db.flush()

    async def _store_gate_fail(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        reason: str,
    ) -> None:
        """Clear old products and store a gate_fail marker."""
        await self.db.execute(text(
            "DELETE FROM panel_selections WHERE tenant_id = :tid AND project_id = :pid"
        ), {"tid": tenant_id, "pid": project_id})
        await self.db.execute(text("""
            INSERT INTO panel_selections
                (tenant_id, project_id, product_code, product_name, quantity,
                 source, question_no, reason)
            VALUES
                (:tid, :pid, 'NONE', NULL, 0, 'gate_fail', NULL, :reason)
        """), {"tid": tenant_id, "pid": project_id, "reason": reason})
        await self.db.flush()

    async def _store_products(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        products: list[dict],
        *,
        panel_group_id: str | None = None,
        skip_delete: bool = False,
    ) -> None:
        """Clear old products and insert new ones."""
        if not skip_delete:
            await self.db.execute(text(
                "DELETE FROM panel_selections WHERE tenant_id = :tid AND project_id = :pid"
            ), {"tid": tenant_id, "pid": project_id})

        for p in products:
            await self.db.execute(text("""
                INSERT INTO panel_selections
                    (tenant_id, project_id, product_code, product_name, quantity,
                     source, question_no, reason, panel_group_id)
                VALUES
                    (:tid, :pid, :code, :name, :qty, :source, :qno, :reason, :gid)
            """), {
                "tid": tenant_id,
                "pid": project_id,
                "code": p["product_code"],
                "name": p.get("product_name"),
                "qty": p["quantity"],
                "source": p["source"],
                "qno": p.get("question_no"),
                "reason": p.get("reason"),
                "gid": panel_group_id,
            })
        await self.db.flush()

    async def _get_product_name(self, code: str) -> str | None:
        """Look up product description from products table."""
        result = await self.db.execute(
            text("SELECT description FROM products WHERE code = :code LIMIT 1"),
            {"code": code},
        )
        row = result.first()
        return row[0] if row else None


# ── Private helpers ──

def _extract_text(response) -> str:
    for item in response.output:
        if getattr(item, "type", None) == "message":
            for block in getattr(item, "content", []):
                if getattr(block, "type", None) == "output_text":
                    return block.text
    raise RuntimeError("GPT-5.2 did not return a text response")


def _parse_json(raw: str) -> dict:
    txt = raw.strip()
    txt = re.sub(r"^```(?:json)?\s*\n?", "", txt)
    txt = re.sub(r"\n?```\s*$", "", txt)
    txt = txt.strip()
    try:
        return json.loads(txt)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse LLM JSON: %s\nRaw: %s", e, raw[:500])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI returned an invalid response. Please try again.",
        )
