"""Device selection service — match BOQ items to selectables using LLM."""

import json
import logging
import math
import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.boq.models import BoqItem, Document
from app.modules.device_selection.schemas import DeviceSelectionResult
from app.modules.projects.models import Project
from app.modules.spec.models import SpecBlock
from app.shared.openai_client import get_openai_client

logger = logging.getLogger(__name__)

_BATCH_SIZE = 45
_PENDING_PANEL_MARKER = "__PENDING_PANEL__"

SYSTEM_PROMPT = """\
You are a fire protection device selection expert. Your task is to match \
each BOQ (Bill of Quantities) item to the single best selectable from the \
provided catalog.

## Instructions

Go through each BOQ item ONE BY ONE, sequentially.

For each BOQ item, search the selectables catalog for the best match:

1. **BOQ match phrases**: Each selectable has multiple synonym phrases \
in its `boq_match_phrases` array and a `category` field. The BOQ item \
does NOT need to match exactly — match semantically. For example, \
"smoke detector" should match a selectable with boq_match_phrases like \
["Photo electric smoke sensor", "Smoke Detector", "Optical Smoke Sensor"].

2. **Specification hints — HIGHEST PRIORITY**: When a selectable has `specification_hints`, \
check the project specification text for those specific indicators. \
If the hints are found in the spec, PRIORITIZE that \
selectable over others — even if another selectable has a closer \
description match. This helps disambiguate between similar selectables \
(e.g., two smoke detectors where one is for high ceilings based on spec hints).

3. **Combo preference**: For detection devices, PREFER combo selectables \
(selection_type="combo") over single. If a combo matches the BOQ item, use \
it. Only fall back to single if no combo fits.

4. **CO sensor rule**: If a BOQ item description mentions "CO sensor", \
"CO detector", or "carbon monoxide", you MUST select the combo selectable \
that contains BOTH a CO sensor. Specifically: \
for MX devices select the combo with product codes 4098-5268 and 4098-5260; \
for IDNet devices select the combo with product codes 4098-9733 and 4098-9770.

5. **Manual pull station / call point consistency**: If a BOQ item is a \
manual pull station or manual call point, and the selected selectable is a \
glass-breakable type, then ALL other manual pull stations / call points in \
the same project must also be matched to glass-breakable type selectables. \
Keep consistency across all pull stations.

6. **Notification device defaults**: For notification appliances: \
(a)  if the BOQ & description does NOT specify color, ressolve it based on the mount type: \
if WALL mounted → default to RED; if CEILING mounted → default to WHITE. \
Only apply these color defaults when the BOQ & description does NOT \
explicitly specify a color. its not necessary if one is red other must be red no. \
(b)if the BOQ & description does NOT specify \
ceiling or wall mount, default to WALL mounted variants. \

7. **Notification device protocol consistency — CRITICAL**: Before matching \
any individual notification BOQ item, you MUST first determine the \
notification protocol. The catalog contains both addressable \
(category "addressable_notification_device") and non-addressable \
(category "non_addressable_notification_device") notification selectables. \
ALL notification items in a project MUST use the SAME protocol — never mix \
addressable and non-addressable notifications. \
\
**Step 1 — Determine protocol from BOQ and specification:** \
Scan ALL notification-related BOQ item descriptions AND the project \
specification text. Determine whether the project needs addressable or \
non-addressable notification devices based on the overall context, \
terminology, and requirements found across both sources. If the BOQ and \
spec indicate addressable notifications (e.g., mentions of "addressable", \
addressable system context, intelligent/networked notification devices), \
set notification_protocol to "addressable". If nothing clearly indicates \
addressable, the default is "non_addressable". \
\
**Step 2 — Default (nothing mentioned):** \
If neither addressable nor non-addressable is clearly indicated anywhere \
in the BOQ or specification for notification devices, default to \
"non_addressable". ALL notification items use non-addressable selectables. \
\
**Step 3 — Exception: explicit non-addressable in BOQ (rare, overrides all):** \
If ANY notification-related BOQ item explicitly says "conventional" or \
"non-addressable" in its text (BOQ item description only — NOT from the \
project specification), then force notification_protocol to \
"non_addressable" regardless of what Step 1 decided. This is rare but \
overrides everything — even if other BOQ items or the spec say \
"addressable". ALL notification items MUST then use non-addressable \
selectables. \
\
You MUST output this decision in the `notification_protocol` field BEFORE \
the matches array.

8. **Notification devices**: No combos exist for notification appliances, \
just match to the best single selectable.

9. **Notification priority preference**: Some notification selectables have \
a `priority` field set to "High". These are the most commonly requested and \
delivered products — roughly 95% of the time, these are the correct choice. \
When choosing between competing notification selectables, PREFER the one \
with priority "High". HOWEVER, if the BOQ description or project \
specification explicitly mentions specific attributes (e.g., a particular \
wattage, mounting style, weatherproofing, or other distinguishing feature) \
that clearly match a selectable WITHOUT high priority, then choose that \
more specific match instead. Explicit BOQ/spec requirements always override \
the priority preference.

10. **Cables / infrastructure / other**: If a BOQ item is clearly a cable, \
conduit, or other non-selectable infrastructure item, return selectable_id \
as null. For fire alarm panels, suppression panels, and release kits — check \
if a conventional_device selectable matches before returning null.

11. **Conventional devices**: The catalog contains conventional (non-addressable) \
devices with category `"conventional_device"`. These include conventional \
detectors, switches, manual pull stations, bells, suppression components, and \
more. A project can use BOTH addressable AND conventional devices \
simultaneously — they are not mutually exclusive. Even detection can be a mix: \
addressable smoke detectors alongside conventional smoke detectors in the same \
project. When a BOQ item clearly describes a conventional/non-addressable \
device (e.g., "conventional smoke detector", "non-addressable heat detector", \
"maintenance switch", "abort switch", "conventional bell", "suppression \
panel"), match it to a conventional_device selectable. Do NOT match \
conventional BOQ items to addressable selectables or vice versa — respect the \
explicit conventional/addressable distinction in the BOQ text. If a BOQ item \
does not specify conventional or addressable, default to the addressable \
selectable (since addressable is the primary system).

12. **Conventional panel lock-in**: If ANY BOQ item in the project is matched \
to a conventional fire alarm control panel (e.g., product code `4004-9302` — \
4 Zone Conventional Panel, or `4007-9101` — Conventional Fire Alarm Control \
Panel), then ALL devices in that project MUST be selected from \
`conventional_device` selectables only. Do NOT mix addressable selectables \
with a conventional panel — if the panel is conventional, every detector, \
switch, notification appliance, and other device must also come from the \
conventional catalog. A conventional panel cannot drive addressable devices.

13. **No specification available**: If no project specification text is provided \
(the specification section is absent or empty), rely entirely on the BOQ item \
descriptions, quantities, and the selectable catalog to make your best match. \
Use the `boq_match_phrases` and `specification_hints` from the selectables \
catalog as your primary matching guide. Set `inferred_from` to 'BOQ' for all \
matches when no spec is available.

14. **No match**: If no selectable in the catalog fits the BOQ item, return \
selectable_id as null. and there is possibility there are some missing selectables for boq.

15. **Annunciators & Subpanels**: The catalog contains annunciator and subpanel \
selectables with category "annunciator_subpanel". These include graphics \
workstations (PC + software + network card), repeater/annunciator LCD panels, \
and mimic/override panels. Key matching rules:
(a) Graphics Workstations — When a BOQ item mentions "graphics", "workstation", \
"PC", "software", or "computer" for fire alarm monitoring, match to an \
annunciator_subpanel selectable. The workstation variant MUST match the \
project's `network_type` determined in rule 16 — same networking type, \
same override decision. Do NOT rely only on `specification_hints` to pick \
the variant — use the resolved `network_type` and override decision from \
rule 16 as the primary selectors. \
Override vs No-Override for workstation selection: \
- Priority: no-override is the DEFAULT and has higher priority. \
- If override is not mentioned anywhere in BOQ or spec → choose no-override. \
- If BOTH override and no-override are mentioned (conflict) → choose no-override. \
- Only choose override variant when override is CLEARLY and EXCLUSIVELY \
mentioned without any conflicting no-override indicators. \
- Override conflicts can come from within BOQ alone, within spec alone, \
or between BOQ and spec.
(b) Repeater / Annunciator Panels — When a BOQ item mentions "annunciator", \
"repeater", or "LCD panel", do NOT pick a specific repeater variant. Instead, \
return selectable_id as "__PENDING_PANEL__" with reason "Repeater panel — \
deferred until panel type is determined". The correct variant depends on the \
main panel series, which is resolved after device selection.
(c) Mimic / Override Panels — When a BOQ item mentions "mimic", "override", \
"AHU override", or "elevator control panel", match to the mimic panel \
selectable. Do not worry about quantity — it is handled by post-processing.

16. **Networking type detection — CRITICAL**: Networking is NOT always needed. \
It is ONLY required when EITHER of these conditions is true: \
(i) A workstation / graphics station exists in the BOQ items, OR \
(ii) Multiple MAIN fire alarm panels exist in the BOQ (note: "main panels" means \
the primary fire alarm control panels, NOT repeaters, annunciators, subpanels, \
or mimic panels). \
If NEITHER condition is true, set `network_type` to null — the project does \
not need networking. \
\
When networking IS needed, determine the type by scanning the ENTIRE BOQ and \
ENTIRE project specification (not just workstation-related items — check \
EVERYTHING). Use semantic/fuzzy matching, not exact keywords, because spelling \
mistakes are common in BOQ and specs. Look for meanings like: \
- Wired/copper concepts: wired, copper, ethernet, CAT5, CAT6, RJ45, RJ-45, \
UTP, network cable, patch panel, copper media, LAN cable, and similar. \
- Fiber concepts: fiber, fibre, fiber optic, fibre optic, optical fiber, \
optical fibre, SM fiber, MM fiber, fiber media, fiber cable, and similar. \
- IP concepts: IP, TCP/IP, IP-based, IP network, IP communication, \
IP gateway, CS gateway, and similar. \
\
**PRIORITY RULES (strictly enforced):** \
Priority 1 (highest): "wired" \
Priority 2: "fiber" \
Priority 3 (lowest): "IP" \
\
**CONFLICT RESOLUTION — a single network type for the entire project:** \
A project uses ONE network type everywhere. If different parts of the BOQ or \
spec mention different networking types, this is a CONFLICT. Resolve conflicts \
by picking the HIGHER priority type: \
- Wired vs Fiber → choose "wired" \
- Wired vs IP → choose "wired" \
- Fiber vs IP → choose "fiber" \
- Wired vs Fiber vs IP → choose "wired" \
- Even if a workstation BOQ item explicitly says "IP workstation" or "fiber \
workstation", but ANYWHERE else in the BOQ or spec wired/copper networking \
is mentioned for any purpose, the conflict resolves to "wired". The \
workstation must then be matched to the wired variant. \
- Same logic applies for fiber vs IP conflicts. \
\
**NO CONFLICT (single type found):** If only one type is mentioned across the \
entire BOQ and spec (e.g., everything says fiber), choose that type. \
\
**NOTHING FOUND:** If networking is needed but no networking type keywords are \
found anywhere, default to "wired" (highest priority). \
\
Output the `network_type` field in the JSON response: one of "fiber", "wired", \
"IP", or null if networking is not needed.

17. **Matching Rule — CRITICAL**: Match based on the actual meaning and purpose of \
the device, not just keyword overlap. A BOQ or spec item must genuinely BE the \
device described by a selectable — not merely share a word with it. For example, \
a "mimic panel" is NOT a detection or notification device, and a "graphic station" \
is NOT a "graphic annunciator".

18. **Spec-only items (workstation & printer)**: After matching ALL BOQ items, check: \
(a) WORKSTATION: If the specification mentions a workstation, graphics station, or \
fire alarm PC, but NO BOQ item was matched to a work_station selectable → add an \
extra entry in matches with boq_item_id set to "SPEC_ADDED_WORKSTATION" and the \
appropriate workstation selectable_id (chosen per rules 15a/16). \
(b) PRINTER: If the specification mentions a printer or printing capability, but \
NO BOQ item description mentions "printer" → add an extra entry with \
boq_item_id set to "SPEC_ADDED_PRINTER" and selectable_id as null. \
If the item IS already in the BOQ — do nothing extra, normal matching applies. Don't apply for other devices even though you find \
in the specs this special feature is for only printer and workstation.

IMPORTANT: You MUST return an entry for EVERY boq_item_id provided, even \
if the match is null. Do not skip any item.

## Output format

Return ONLY valid JSON (no markdown fences):
{"notification_protocol": "<addressable or non_addressable or null if no notification items>", "network_type": "<fiber or wired or IP or null>", "matches": [{"boq_item_id": "<uuid>", "selectable_id": "<uuid or null>", "reason": "<short sentence explaining why this selectable was chosen, or why null>"}]}

The `notification_protocol` and `network_type` fields MUST appear before `matches`. \
Decide them first by scanning all BOQ items and spec text, then use those decisions \
to constrain all matches. `network_type` is null when networking is not needed \
(no workstation and no multiple main panels). When networking IS needed but type \
is unclear, default to "wired".
"""


def _build_user_message(
    boq_items_json: str,
    selectables_json: str,
    spec_text: str | None,
) -> str:
    parts = [
        "## BOQ Items to match\n",
        boq_items_json,
        "\n\n## Selectables Catalog\n",
        selectables_json,
    ]
    if spec_text:
        parts.append("\n\n## Project Specification Text\n")
        parts.append(spec_text)
    return "".join(parts)


class DeviceSelectionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def run(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> DeviceSelectionResult:
        # ── 1. Load ALL BOQ items (no category filter) ──
        boq_result = await self.db.execute(
            select(BoqItem)
            .where(
                BoqItem.tenant_id == tenant_id,
                BoqItem.project_id == project_id,
                BoqItem.type == "boq_item",
            )
            .order_by(BoqItem.row_number.asc())
        )
        boq_items = list(boq_result.scalars().all())

        if not boq_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No BOQ items found. Extract BOQ first.",
            )

        # ── 2. Determine protocol from analysis answers ──
        protocol = await self._get_protocol(tenant_id, project_id)
        if not protocol:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Protocol not determined yet. Run spec analysis first.",
            )

        # MX protocol → exclude idnet detection devices
        # IDNET protocol → exclude mx detection devices
        exclude_category = (
            "idnet_detection_device" if protocol == "MX"
            else "mx_detection_device"
        )
        logger.info("Device selection: protocol=%s, excluding %s", protocol, exclude_category)

        # ── 3. Load selectables with product info (filtered by protocol) ──
        selectables_rows = await self.db.execute(text("""
            SELECT
                s.id,
                s.category,
                s.selection_type,
                s.boq_match_phrases,
                s.description,
                s.specification_hints,
                s.priority,
                COALESCE(
                    array_agg(DISTINCT p.code) FILTER (WHERE p.code IS NOT NULL),
                    '{}'
                ) AS product_codes,
                COALESCE(
                    array_agg(DISTINCT p.description) FILTER (WHERE p.description IS NOT NULL),
                    '{}'
                ) AS product_descriptions
            FROM selectables s
            LEFT JOIN selectable_products sp ON sp.selectable_id = s.id
            LEFT JOIN products p ON p.id = sp.product_id
            WHERE s.category != :exclude_cat
            GROUP BY s.id, s.category, s.selection_type,
                     s.boq_match_phrases, s.description, s.specification_hints, s.priority
        """), {"exclude_cat": exclude_category})
        selectables_data = selectables_rows.fetchall()

        if not selectables_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No selectables found in the system. Seed selectables first.",
            )

        # Build lookup and catalog
        selectable_lookup: dict[str, dict] = {}
        catalog_for_llm: list[dict] = []

        for row in selectables_data:
            sid = str(row.id)
            p_codes = list(row.product_codes) if row.product_codes else []
            p_descs = list(row.product_descriptions) if row.product_descriptions else []

            selectable_lookup[sid] = {
                "selection_type": row.selection_type,
                "product_codes": p_codes,
                "product_descriptions": p_descs,
            }

            entry = {
                "id": sid,
                "category": row.category,
                "selection_type": row.selection_type,
                "boq_match_phrases": list(row.boq_match_phrases) if row.boq_match_phrases else [],
                "specification_hints": row.specification_hints,
            }
            if row.description:
                entry["description"] = row.description
            if row.priority:
                entry["priority"] = row.priority
            catalog_for_llm.append(entry)

        # ── 4. Load spec text ──
        spec_text = await self._load_spec_text(tenant_id, project_id)

        # ── 5. Batch and call LLM ──
        all_matches: list[dict] = []
        network_type: str | None = None
        selectables_json = json.dumps(catalog_for_llm, ensure_ascii=False)

        for i in range(0, len(boq_items), _BATCH_SIZE):
            batch = boq_items[i : i + _BATCH_SIZE]
            batch_json = json.dumps(
                [{"id": str(item.id), "description": item.description} for item in batch],
                ensure_ascii=False,
            )

            user_msg = _build_user_message(batch_json, selectables_json, spec_text)

            logger.info(
                "Device selection: calling LLM for batch %d-%d of %d items",
                i + 1,
                min(i + _BATCH_SIZE, len(boq_items)),
                len(boq_items),
            )

            client = get_openai_client()
            response = await client.responses.create(
                model="gpt-5.2",
                instructions=SYSTEM_PROMPT,
                input=[{"role": "user", "content": user_msg}],
            )

            raw_text = _extract_text(response)
            parsed = _parse_json(raw_text)

            if isinstance(parsed, dict) and "matches" in parsed:
                all_matches.extend(parsed["matches"])
                if "notification_protocol" in parsed:
                    logger.info(
                        "Device selection batch %d: notification_protocol=%s",
                        i, parsed["notification_protocol"],
                    )
                if "network_type" in parsed:
                    network_type = parsed["network_type"]
                    logger.info(
                        "Device selection batch %d: network_type=%s",
                        i, network_type,
                    )
            else:
                logger.warning("Unexpected LLM response format for batch starting at %d", i)

        # ── 5a. Handle spec-added items (workstation & printer) ──
        spec_added_markers = [
            m for m in all_matches
            if m.get("boq_item_id") in ("SPEC_ADDED_WORKSTATION", "SPEC_ADDED_PRINTER")
        ]
        if spec_added_markers:
            # Get the BOQ document for this project
            boq_doc_result = await self.db.execute(
                select(Document).where(
                    and_(
                        Document.tenant_id == tenant_id,
                        Document.project_id == project_id,
                        Document.type == "BOQ",
                    )
                ).limit(1)
            )
            boq_doc = boq_doc_result.scalar_one_or_none()
            if boq_doc:
                # Get max row_number to assign new rows after existing ones
                max_row_result = await self.db.execute(
                    text(
                        "SELECT COALESCE(MAX(row_number), 0) FROM boq_items"
                        " WHERE project_id = :pid AND tenant_id = :tid"
                    ),
                    {"pid": project_id, "tid": tenant_id},
                )
                next_row = (max_row_result.scalar() or 0) + 1

                for match in spec_added_markers:
                    marker = match["boq_item_id"]
                    if marker == "SPEC_ADDED_WORKSTATION":
                        desc = "Workstation (added from specification)"
                    else:
                        desc = "Printer (added from specification)"

                    new_item = BoqItem(
                        tenant_id=tenant_id,
                        project_id=project_id,
                        document_id=boq_doc.id,
                        row_number=next_row,
                        description=desc,
                        quantity=1,
                        type="boq_item",
                    )
                    self.db.add(new_item)
                    await self.db.flush()

                    real_id = str(new_item.id)
                    match["boq_item_id"] = real_id
                    boq_items.append(new_item)

                    logger.info(
                        "Spec-added %s: created BoqItem %s (row %d)",
                        marker, real_id, next_row,
                    )
                    next_row += 1
            else:
                logger.warning(
                    "No BOQ document found — cannot create spec-added items"
                )
                # Remove markers since we can't create items for them
                all_matches = [
                    m for m in all_matches
                    if m.get("boq_item_id")
                    not in ("SPEC_ADDED_WORKSTATION", "SPEC_ADDED_PRINTER")
                ]

        # ── 5b. Store network_type on the project ──
        # Only store if LLM returned a valid type (networking is needed).
        # If null → no networking needed, keep project.network_type as NULL.
        if network_type and str(network_type).lower() in ("fiber", "wired", "ip"):
            clean_network_type = str(network_type).lower()
            if clean_network_type == "ip":
                clean_network_type = "IP"
            await self.db.execute(
                text("UPDATE projects SET network_type = :nt, network_type_auto = :nt WHERE id = :pid AND tenant_id = :tid"),
                {"nt": clean_network_type, "pid": project_id, "tid": tenant_id},
            )
            logger.info("Device selection: stored network_type=%s for project %s", clean_network_type, project_id)
        else:
            # No networking needed (no workstation, no multiple main panels) — clear any previous value
            await self.db.execute(
                text("UPDATE projects SET network_type = NULL, network_type_auto = NULL WHERE id = :pid AND tenant_id = :tid"),
                {"pid": project_id, "tid": tenant_id},
            )
            logger.info("Device selection: network_type=NULL (not needed) for project %s", project_id)

        # ── 6. Delete old selections and store new ──
        await self.db.execute(
            text("DELETE FROM boq_device_selections WHERE tenant_id = :tid AND project_id = :pid"),
            {"tid": tenant_id, "pid": project_id},
        )
        await self.db.flush()

        # Build a lookup from LLM matches: boq_item_id → (selectable_id, reason)
        llm_match_map: dict[str, tuple[str | None, str | None]] = {}
        for match in all_matches:
            bid = match.get("boq_item_id")
            if bid:
                llm_match_map[bid] = (match.get("selectable_id"), match.get("reason"))

        # Insert a row for EVERY BOQ item — matched or not
        matched_count = 0
        for item in boq_items:
            item_id = str(item.id)
            selectable_id, reason = llm_match_map.get(item_id, (None, None))

            # Detect deferred repeater panel marker from LLM
            if selectable_id == _PENDING_PANEL_MARKER:
                selectable_id = None
                row_status = "pending_panel"
                deferred_type = "repeater_panel"
                sel_type = "none"
                p_codes: list[str] = []
                p_descs: list[str] = []
            else:
                sel_info = selectable_lookup.get(selectable_id) if selectable_id else None
                if selectable_id and not sel_info:
                    logger.warning("LLM returned unknown selectable_id %s — treating as null", selectable_id)
                    selectable_id = None
                sel_type = sel_info["selection_type"] if sel_info else "none"
                p_codes = sel_info["product_codes"] if sel_info else []
                p_descs = sel_info["product_descriptions"] if sel_info else []
                row_status = "finalized" if selectable_id else "no_match"
                deferred_type = None

            if selectable_id:
                matched_count += 1

            await self.db.execute(text("""
                INSERT INTO boq_device_selections
                    (tenant_id, project_id, boq_item_id, selectable_id,
                     selection_type, product_codes, product_descriptions, reason,
                     status, deferred_type)
                VALUES
                    (:tenant_id, :project_id, :boq_item_id, :selectable_id,
                     :selection_type, :product_codes, :product_descriptions, :reason,
                     :status, :deferred_type)
                ON CONFLICT (boq_item_id) DO UPDATE SET
                    selectable_id = EXCLUDED.selectable_id,
                    selection_type = EXCLUDED.selection_type,
                    product_codes = EXCLUDED.product_codes,
                    product_descriptions = EXCLUDED.product_descriptions,
                    reason = EXCLUDED.reason,
                    status = EXCLUDED.status,
                    deferred_type = EXCLUDED.deferred_type,
                    updated_at = now()
            """), {
                "tenant_id": tenant_id,
                "project_id": project_id,
                "boq_item_id": item_id,
                "selectable_id": selectable_id,
                "selection_type": sel_type,
                "product_codes": p_codes,
                "product_descriptions": p_descs,
                "reason": reason,
                "status": row_status,
                "deferred_type": deferred_type,
            })

        await self.db.flush()

        # ── 7. Post-processing: mimic panel quantity override ──
        await self._apply_mimic_panel_override(tenant_id, project_id)

        return DeviceSelectionResult(
            project_id=project_id,
            status="success",
            message=f"Device selection complete. {matched_count} of {len(boq_items)} items matched.",
            matched_count=matched_count,
        )

    async def _apply_mimic_panel_override(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> None:
        """Post-processing: recalculate mimic panel quantity from control modules.

        Mimic panel quantity = ceil(total_control_modules / 64).
        """
        # 1. Find the mimic panel selectable
        mimic_result = await self.db.execute(text("""
            SELECT id FROM selectables
            WHERE category = 'annunciator_subpanel'
            AND boq_match_phrases @> ARRAY['Mimic']
        """))
        mimic_sel_id = mimic_result.scalar_one_or_none()
        if not mimic_sel_id:
            return

        # 2. Check if any BOQ item was matched to the mimic panel
        match_result = await self.db.execute(text("""
            SELECT bds.boq_item_id
            FROM boq_device_selections bds
            WHERE bds.tenant_id = :tid
            AND bds.project_id = :pid
            AND bds.selectable_id = :mimic_id
            LIMIT 1
        """), {"tid": tenant_id, "pid": project_id, "mimic_id": str(mimic_sel_id)})
        mimic_match = match_result.scalar_one_or_none()
        if not mimic_match:
            return

        mimic_boq_item_id = str(mimic_match)

        # 3. Find all control module selectable IDs
        cm_result = await self.db.execute(text("""
            SELECT id FROM selectables
            WHERE category IN ('idnet_detection_device', 'mx_detection_device')
            AND boq_match_phrases @> ARRAY['Control Module']
        """))
        cm_sel_ids = [str(row[0]) for row in cm_result]
        if not cm_sel_ids:
            logger.warning("Mimic panel matched but no control module selectables found")
            return

        # 4. Sum BOQ quantities matched to control module selectables
        total_result = await self.db.execute(text("""
            SELECT COALESCE(SUM(bi.quantity), 0)
            FROM boq_device_selections bds
            JOIN boq_items bi ON bi.id = bds.boq_item_id
            WHERE bds.tenant_id = :tid
            AND bds.project_id = :pid
            AND bds.selectable_id = ANY(:cm_ids)
        """), {"tid": tenant_id, "pid": project_id, "cm_ids": cm_sel_ids})
        total_control_modules = total_result.scalar() or 0

        if total_control_modules == 0:
            logger.warning(
                "Mimic panel matched but no control module BOQ quantities found — skipping override"
            )
            return

        # 5. Calculate new quantity
        new_qty = math.ceil(total_control_modules / 64)
        logger.info(
            "Mimic panel quantity override: %d control modules / 64 = %d",
            total_control_modules,
            new_qty,
        )

        # 6. Update the BOQ item quantity
        await self.db.execute(text("""
            UPDATE boq_items
            SET quantity = :new_qty
            WHERE id = :boq_item_id
        """), {"new_qty": new_qty, "boq_item_id": mimic_boq_item_id})
        await self.db.flush()

    async def _get_protocol(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> str | None:
        """Read protocol directly from projects table."""
        result = await self.db.execute(
            select(Project.protocol).where(
                Project.id == project_id,
                Project.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def _load_spec_text(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> str | None:
        """Load spec blocks for the project and concatenate content."""
        # Find the spec document
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

        # Get all spec blocks
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


# ── Private helpers ──

def _extract_text(response) -> str:
    for item in response.output:
        if getattr(item, "type", None) == "message":
            for block in getattr(item, "content", []):
                if getattr(block, "type", None) == "output_text":
                    return block.text
    raise RuntimeError("GPT-5.2 did not return a text response")


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse LLM JSON: %s\nRaw: %s", e, raw[:500])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI returned an invalid response. Please try again.",
        )
