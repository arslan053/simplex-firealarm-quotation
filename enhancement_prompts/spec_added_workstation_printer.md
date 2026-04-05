# Enhancement: Spec-Added Workstation & Printer BOQ Items + Semantic Matching Rule

## Context

The device selection pipeline matches BOQ items to product selectables using an LLM. Currently, if a project specification mentions a workstation or printer but the BOQ doesn't include it, the system misses it entirely — no BOQ item exists, so device selection can't match it and panel selection can't see it.

This creates two gaps:

- **Workstation**: Panel selection needs to see a workstation BOQ item to make networking/printer decisions. If the spec calls for one but the BOQ omits it, panel selection operates with incomplete information.
- **Printer**: Panel selection Q14 ("Does the BOQ mention a printer?") can only answer "Yes" if a printer BOQ item exists. If the spec mentions a printer but the BOQ doesn't, the printer card never gets added.

Also, the device selection prompt currently lacks a semantic matching rule that panel_selection and spec_analysis already have — this can lead to false matches based on keyword overlap (e.g., "mimic panel" matching to a detection device, or "graphic station" matching "graphic annunciator").

**Only `backend/app/modules/device_selection/service.py` needs changes. No migrations, no seeds, no frontend changes.**

---

## What to Implement

### 1. Add Prompt Rule 17: Semantic Matching Rule

In `SYSTEM_PROMPT`, after rule 16 (networking type detection) and before the "IMPORTANT:" line, add rule 17:

```
17. **Matching Rule — CRITICAL**: Match based on the actual meaning and purpose of
the device, not just keyword overlap. A BOQ or spec item must genuinely BE the
device described by a selectable — not merely share a word with it. For example,
a "mimic panel" is NOT a detection or notification device, and a "graphic station"
is NOT a "graphic annunciator".
```

This matches the same semantic matching rule already present in panel_selection and spec_analysis prompts.

### 2. Add Prompt Rule 18: Spec-Only Workstation & Printer Detection

After rule 17, add rule 18:

```
18. **Spec-only items (workstation & printer)**: After matching ALL BOQ items, check:
(a) WORKSTATION: If the specification mentions a workstation, graphics station, or
fire alarm PC, but NO BOQ item was matched to a work_station selectable → add an
extra entry in matches with boq_item_id set to "SPEC_ADDED_WORKSTATION" and the
appropriate workstation selectable_id (chosen per rules 15a/16).
(b) PRINTER: If the specification mentions a printer or printing capability, but
NO BOQ item description mentions "printer" → add an extra entry with
boq_item_id set to "SPEC_ADDED_PRINTER" and selectable_id as null.
If the item IS already in the BOQ — do nothing extra, normal matching applies.
```

The LLM uses special marker strings (`SPEC_ADDED_WORKSTATION`, `SPEC_ADDED_PRINTER`) as `boq_item_id` values so the backend can detect and handle them.

### 3. Add Post-LLM Code: Create Spec-Added BoqItems (Step 5a)

In the `run()` method of `DeviceSelectionService`, after all LLM batches complete and `all_matches` is populated, but **before** step 5b (store network_type), add a new step 5a:

1. **Scan** `all_matches` for entries with `boq_item_id` equal to `"SPEC_ADDED_WORKSTATION"` or `"SPEC_ADDED_PRINTER"`.

2. If any markers found:
   - **Get the BOQ document** for this project (`Document.type == "BOQ"`, same tenant/project).
   - **Get `max(row_number)`** from existing `boq_items` for this project to assign new row numbers after existing items.
   - **For each marker**, create a new `BoqItem`:
     - `description`: `"Workstation (added from specification)"` or `"Printer (added from specification)"`
     - `quantity`: `1`
     - `type`: `"boq_item"`
     - `row_number`: next available row
     - `document_id`: the BOQ document's ID
   - **Flush** to get the real UUID from the database.
   - **Replace** the marker string in `match["boq_item_id"]` with the real UUID.
   - **Append** the new `BoqItem` to the `boq_items` list so step 6 (match storage loop) processes it normally.
   - **Log** what was created at INFO level.

3. If no BOQ document found (edge case): log a warning and remove the marker entries from `all_matches` so they don't cause errors in step 6.

Step 6 (match storage loop) already iterates `boq_items` and uses `llm_match_map` — the new items will be stored with their device selection records automatically, no changes needed there.

---

## Behavior Summary

| Scenario | What happens |
|---|---|
| Spec mentions workstation, BOQ has workstation | Normal matching — no extra item |
| Spec mentions workstation, BOQ doesn't have one | New BoqItem created (qty 1), matched to proper workstation selectable |
| Spec mentions printer, BOQ has printer | Normal matching — no extra item |
| Spec mentions printer, BOQ doesn't have one | New BoqItem created (qty 1), selectable_id null (panel Q14 picks it up) |
| No spec available | No spec-added items (nothing to detect from) |
| Panel selection runs later | Reads `boq_items` table — sees all items including spec-added ones |

---

## Files to Modify

| File | Change |
|------|--------|
| `backend/app/modules/device_selection/service.py` | Add prompt rules 17 + 18 to `SYSTEM_PROMPT`, add step 5a post-LLM code to create spec-added BoqItems in `run()` |

No migrations needed — uses existing `boq_items` and `documents` tables.
No seeds needed.
No frontend changes.

---

## How to Re-apply This Enhancement

If you need to re-implement this from scratch:

1. **Add rule 17** to `SYSTEM_PROMPT` — semantic matching rule, placed after rule 16 and before "IMPORTANT:".

2. **Add rule 18** to `SYSTEM_PROMPT` — spec-only workstation & printer detection using `SPEC_ADDED_WORKSTATION` and `SPEC_ADDED_PRINTER` marker strings as `boq_item_id`.

3. **Add step 5a** in the `run()` method between the batch loop and step 5b:
   - Scan `all_matches` for marker entries.
   - Query for BOQ `Document` (type `"BOQ"`, same tenant/project).
   - Query `max(row_number)` for new row assignment.
   - Create `BoqItem` for each marker (qty=1, appropriate description).
   - Flush to get UUID, replace marker with real UUID, append to `boq_items`.
   - Handle missing BOQ document gracefully (warn + remove markers).

4. **No other changes needed** — step 6 and post-processing handle the new items automatically since they're appended to `boq_items` and their matches are in `llm_match_map`.

---

## Key Design Decisions

- **Markers in LLM output** — using string markers (`SPEC_ADDED_WORKSTATION`, `SPEC_ADDED_PRINTER`) instead of asking the LLM to create real UUIDs avoids hallucinated IDs and makes detection trivial in code.
- **BoqItem creation in service, not migration** — these are runtime items created per-project when needed, not seed data.
- **Printer selectable_id is null** — printers don't have a selectable in the catalog; the BOQ item's mere existence is what panel selection Q14 checks for.
- **Workstation gets a real selectable_id** — the LLM picks the correct workstation variant per rules 15a/16 (networking type, override decision), same as if it were a real BOQ item.
- **Appending to `boq_items` list** — ensures step 6 processes spec-added items identically to real BOQ items, no special-casing needed downstream.
- **Quantity = 1** — reasonable default for a spec-mentioned item not quantified in the BOQ.
