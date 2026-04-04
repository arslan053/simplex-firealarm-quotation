# Enhancement: Multi-Panel Loop Groups — Per-Group Panel Type Selection

## Problem Statement

Currently, the panel selection pipeline treats **all panels in a project as the same type**. It takes the total detection devices, divides by panel count, and picks **one** panel type (4007 / 4010 / 4100ES) for the entire project.

However, real-world BOQs often contain **multiple panel lines with different loop counts** in the same project. For example:

| BOQ Line | Description | Qty |
|----------|-------------|-----|
| 7 | 2 Loop fire alarm control panel | 1 |
| 8 | Fire Alarm Control Panel 4 Loop | 5 |
| 9 | Fire Alarm Control Panel 6 Loop | 16 |
| 10 | 12 Loop Fire Alarm Control Panel | 6 |

Under the current logic, Q21 returns "12" (the largest), triggering 4100ES for **all 28 panels** — even the single 2-loop panel that should be a 4007.

The system needs to handle each distinct panel line as its own **panel group**, selecting the appropriate panel type per group based on its loop count, while designating one panel as the **main panel** that receives all accessories and child cards.

---

## CRITICAL CONSTRAINT: Do Not Disturb Existing System

The existing panel selection pipeline is **production-ready and correct** for single-panel and same-type-panel scenarios. This enhancement MUST NOT change the existing behavior in any way.

**Activation rule:** The multi-panel-group logic ONLY activates when **ALL** of these conditions are true:

1. **>= 2 distinct loop counts** detected from BOQ panel items — via LLM Q21 answer (primary) or regex fallback
2. Q2 (speakers/amplifiers) = **No**
3. Q3 (telephone/FFT) = **No**

Detection priority: the LLM examines all BOQ items and extracts loop counts (handles word-based like "two loops", "dual loop"). If the LLM finds < 2 distinct loops, a regex fallback scans panel BOQ items for digit-based patterns ("2-loop", "4-loop").

If ANY condition is not met, the **existing system runs unchanged**:

```
Q21 LLM found >= 2 distinct loop counts?
  |
  +-- No --> Regex fallback found >= 2 distinct loop counts?
  |            |
  |            +-- No  --> EXISTING SYSTEM (single-panel path)
  |            +-- Yes --> continue below
  |
  +-- Yes --> continue below
       |
       Q2 (speakers) = Yes OR Q3 (telephone) = Yes?
         |
         +-- Yes --> ALL panels = 4100ES via EXISTING 4100ES path (unchanged)
         |
         +-- No  --> Multi-panel-group logic
```

---

## The Four Core Rules

### Rule 1: Activation — LLM Q21 Primary, Regex Fallback

The LLM answers Q21 with a JSON array of `{boq_item_id, loop_count}` entries extracted from BOQ panel items. The backend validates these against real BOQ data and checks for >= 2 distinct loop counts. If the LLM misses them (returns scalar, empty, or < 2 distinct), a regex fallback scans panel BOQ descriptions for digit-based loop patterns. If neither source finds >= 2 distinct loop counts, the existing single-panel system handles it.

### Rule 2: Speaker/Telephone Override — All 4100ES

If Q2 (speakers/amplifiers) = Yes OR Q3 (telephone/FFT) = Yes, then **ALL panels become 4100ES** regardless of loop counts. The multi-panel-group logic does NOT activate. The existing 4100ES path runs as-is.

### Rule 3: Loop Count Decides Panel Type — Ignore Device Count

When multi-panel-group mode is active, each group's panel type is decided **purely by its loop count**. The `devices_per_panel` calculation is **completely ignored** in this path.

| Loop Count | Panel Type |
|-----------|-----------|
| 1-2 loops | **4007** |
| 3-6 loops | **4010** |
| 7+ loops | **4100ES** |

Even if a 2-loop panel has 290 devices allocated to it (which would normally push it to 4010 range), it stays **4007** because loops override device count in multi-panel-group mode.

### Rule 4: One Main Panel — Accessories Only for Main

One panel group is designated as the **main panel**. The most sophisticated panel type gets main panel priority:

| Priority | Panel Type |
|----------|-----------|
| 1 (highest) | 4100ES |
| 2 | 4010 (2-bay) |
| 3 | 4010 (1-bay) |
| 4 (lowest) | 4007 |

If multiple groups share the highest priority panel type, the one with the **most loops** is the main panel. If still tied, the one with the **highest quantity** is the main panel.

**Only the main panel receives:**
- NAC / Notification cards (with new loop-based rule, see below)
- Mimic panel connection
- Repeater panel connection
- Printer card (with existing workstation logic)
- BMS integration cards
- Networking cards
- Power supplies, enclosures, and all cascading accessories

**All other (non-main) panels receive:**
- Base unit only (from `PANEL_CONFIGS[panel_type]["base_unit_map"][(protocol, notification_type)]`)
- Multiplied by the group's quantity
- No child cards, no accessories, no networking, no anything else

---

## NAC Card Calculation Change (4100ES Main Panel Only)

This is the **only calculation that changes** from the existing system. Everything else stays exactly as-is.

### Current Rule (single-panel mode — unchanged):
```python
qty_nac = math.ceil(hornflasher_count / 45)
```

### New Rule (multi-panel-group mode, 4100ES main panel only):
```python
qty_nac = math.ceil(main_panel_loops / 6)
```

| Main Panel Loops | NAC Cards |
|-----------------|-----------|
| 6 | 1 |
| 7-12 | 2 |
| 13-18 | 3 |
| 19-24 | 4 |

- Product codes remain the same: `4100-5450` (conventional) or `4100-5451` (addressable)
- This rule is based on loop count, not hornflasher count

### When Main Panel is 4007 or 4010:

**No NAC cards needed.** These panel types have built-in notification capacity. Their existing product builders (base unit configs) already handle notification internally. No separate NAC card products are selected.

---

## Single-Panel Flow (When Multi-Group Does NOT Activate)

```
1. BOQ Extraction          --> boq_items table (panels categorized as 'panel')
2. Spec Analysis           --> protocol (MX/IDNET), panel count (Q101/Q102/Q103)
3. Device Selection        --> boq_device_selections, network_type, notification_protocol
4. Panel Selection         --> SINGLE panel type for entire project
   a. Compute: total_devices / panel_count = devices_per_panel
   b. Q21: per-item loop extraction → _derive_max_loop_count() for single value
   c. Check 4100ES triggers (devices>=1000, speakers, telephone, loops>6)
   d. If no triggers: map devices_per_panel to 4007/4010 range
   e. Build ONE product list for all panels
5. Store products          --> panel_selections table (flat list)
```

---

## Implemented Flow

```
1. BOQ Extraction          --> boq_items table (panels categorized as 'panel')
2. Spec Analysis           --> protocol, panel count
3. Device Selection        --> boq_device_selections (unchanged)
4. Panel Selection
   a. LLM call answers all questions (Q2, Q3, Q14, Q17, Q18, Q20, Q21, Q201-Q206)
   b. Q21 answer is parsed as a JSON array of per-item loop extractions
      via _parse_q21_loop_items() → list of {boq_item_id, description, loop_count, quantity}
   c. loop_count = max(loop_counts) via _derive_max_loop_count() (for 4100ES entry gate)
   d. Check Q2/Q3 gates first
   e. Multi-group detection (LLM primary, regex fallback):
      |
      +-- Q21 found >= 2 distinct loop counts? --> Use LLM results
      |
      +-- Q21 found < 2? --> Regex fallback (_detect_panel_groups_regex)
           |
           +-- Regex found >= 2 distinct loop counts? --> Use regex results
           |
           +-- Neither found >= 2 --> EXISTING single-panel path
      |
      +-- >= 2 distinct loop counts from either source:
           i.   Per group: loops --> panel type (Rule 3)
           ii.  Designate main panel (Rule 4)
           iii. Main panel: run existing product builder with NAC change
           iv.  Other panels: base unit + networking x qty
           v.   Combine all products, tagged by group

5. Store products          --> panel_selections table (with panel_group_id)
6. Resolve deferred repeaters --> for main panel type (existing logic)
```

---

## Panel Group Detection — LLM Primary, Regex Fallback

### How It Works

The LLM answers Q21 with a **JSON array** in the `answer` field. Each element identifies one BOQ panel item and its loop count. The backend parses this array, validates each entry against real BOQ items, and uses the result for multi-group detection.

If the LLM fails to extract >= 2 distinct loop counts (e.g. old-format scalar answer, malformed JSON, or only 1 loop count found), a **regex fallback** (`_detect_panel_groups_regex`) scans panel-category BOQ items using the pattern `(\d+)\s*[-–]?\s*loop`. This catches digit-based patterns ("2-loop", "4-loop") but NOT word-based numbers.

The LLM approach is preferred because it handles word-based numbers ("two loops", "dual loop", "twelve loop") that regex cannot match.

### Q21 Answer Format

Q21 returns a JSON array as a string in the `answer` field:

```json
{
  "question_no": 21,
  "answer": "[{\"boq_item_id\": \"uuid-of-row-7\", \"loop_count\": 2}, {\"boq_item_id\": \"uuid-of-row-8\", \"loop_count\": 4}, {\"boq_item_id\": \"uuid-of-row-9\", \"loop_count\": 6}, {\"boq_item_id\": \"uuid-of-row-10\", \"loop_count\": 12}]",
  "confidence": "High"
}
```

The `answer` field is the JSON array itself. The backend:
1. Parses it via `_parse_q21_loop_items(q21_raw, boq_items)` — validates IDs, pulls description and quantity from actual BOQ data (not LLM)
2. Derives `loop_count = max(loop_counts)` via `_derive_max_loop_count()` for the 4100ES entry gate (loops > 6)
3. Checks if >= 2 distinct `loop_count` values exist for multi-group activation

### Backward Compatibility

If Q21 returns an old scalar format (e.g. `"4"`), `json.loads("4")` produces an `int`, `isinstance(items, list)` fails, `_parse_q21_loop_items()` returns `[]`, and the system falls through to regex fallback. Zero breakage during transition — code can be deployed before or after the Q21 question text is updated in the database.

---

## Database Changes

### New Table: `panel_groups`

```sql
CREATE TABLE panel_groups (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    project_id      UUID NOT NULL REFERENCES projects(id),
    boq_item_id     UUID REFERENCES boq_items(id) ON DELETE SET NULL,
    description     TEXT,
    loop_count      INTEGER NOT NULL,
    quantity        INTEGER NOT NULL DEFAULT 1,
    panel_type      VARCHAR(20),          -- '4007', '4010_1bay', '4010_2bay', '4100ES'
    is_main         BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_panel_groups_project ON panel_groups (tenant_id, project_id);
```

### Modify Table: `panel_selections`

Add a nullable `panel_group_id` column to tag products by group:

```sql
ALTER TABLE panel_selections
ADD COLUMN panel_group_id UUID REFERENCES panel_groups(id) ON DELETE SET NULL;
```

When `panel_group_id` is NULL, it means the existing single-panel system produced the row (backward compatible). When populated, the product belongs to a specific panel group.

---

## Per-Group Product Building

### Main Panel Group (4100ES example)

Runs the **existing** `_build_4100es_products()` method (or `_run_4100es()` flow) with:
- `num_panels` = the main group's quantity (e.g. 6)
- All existing parameters (protocol, notification_type, network_type, answer_map, etc.)
- **NAC card change:** NAC card qty = `ceil(main_panel_loops / 6)` instead of `ceil(hornflasher_count / 45)`
- **Loop card change:** Loop card qty = the group's `loop_count` directly (not `ceil(devices / 150 or 200)`). See `loop_card_count_from_q21_loops.md` for details.
- All other steps (controller, audio, telephone, printer, BMS, networking, PSU, enclosures) remain exactly as-is

### Main Panel Group (4010 or 4007 — when no 4100ES exists)

Runs the **existing** 4007/4010 product builder path with:
- `panel_type` = the main group's panel type
- `num_panels` = the main group's quantity
- All child card questions (Q14, Q17, Q18, Q20, Q204) applied normally
- Networking, printer, BMS applied normally
- **No NAC card changes** (4007/4010 have built-in capacity)

### Non-Main Panel Groups

For each non-main group, select **only the base unit**:

```python
config = PANEL_CONFIGS[group.panel_type]
base_products = config["base_unit_map"].get((protocol, notification_type))
if base_products:
    for code, qty_per_panel in base_products:
        products.append({
            "product_code": code,
            "quantity": qty_per_panel * group.quantity,
            "source": "base_unit",
            "reason": f"{group.panel_type} base unit for {group.loop_count}-loop panel",
        })
```

No child cards, no networking, no printer, no BMS, no accessories. For non-main panels, all accessory-related questions are effectively treated as "No" / null.

### 4010 Bay Decision for Multi-Panel Mode

When a group has 3-6 loops and maps to 4010, determine 1-bay vs 2-bay:
- 3-4 loops → `4010_1bay`
- 5-6 loops → `4010_2bay`

This replaces the device-count-based range check (250-500 vs 500-1000) which is irrelevant in multi-panel-group mode since we ignore device count.

---

## Deferred Repeater Panel Resolution

The existing deferred repeater resolution (`_resolve_deferred_repeaters()`) uses the **main panel type** as the resolution key. In multi-panel-group mode, this remains unchanged — repeater panels are resolved to match the **main panel's** series.

---

## Frontend Display

### Current Display (single panel — unchanged):

One flat product table with all products listed.

### New Display (multi-panel-group mode):

Each panel group shown as a **separate section**, top to bottom:

```
+-----------------------------------------------------+
| BOQ: "2 Loop fire alarm control panel" (qty: 1)     |
| Panel Type: 4007                                     |
| +--------------------------------------------------+|
| | Product Code | Description    | Qty | Source     ||
| | 4007-9101    | FACP Base Unit | 1   | base_unit ||
| +--------------------------------------------------+|
+-----------------------------------------------------+

+-----------------------------------------------------+
| BOQ: "Fire Alarm Control Panel 4 Loop" (qty: 5)     |
| Panel Type: 4010 (1-Bay)                             |
| +--------------------------------------------------+|
| | Product Code | Description    | Qty | Source     ||
| | 4010-9501    | FACP Base Unit | 5   | base_unit ||
| | 4010-9929    | Loop Card      | 5   | base_unit ||
| +--------------------------------------------------+|
+-----------------------------------------------------+

+-----------------------------------------------------+
| BOQ: "Fire Alarm Control Panel 6 Loop" (qty: 16)    |
| Panel Type: 4010 (2-Bay)                             |
| +--------------------------------------------------+|
| | Product Code | Description    | Qty | Source     ||
| | 4010-9521    | FACP Base Unit | 16  | base_unit ||
| | 4010-9929    | Loop Card      | 32  | base_unit ||
| +--------------------------------------------------+|
+-----------------------------------------------------+

+-----------------------------------------------------+
| BOQ: "12 Loop Fire Alarm Control Panel" (qty: 6)    |
| Panel Type: 4100ES  ** MAIN PANEL **                 |
| +--------------------------------------------------+|
| | Product Code | Description      | Qty | Source   ||
| | 4100-9701    | Controller       | 6   | step_2   ||
| | 4100-3109    | Loop Card        | 21  | step_4   ||
| | 4100-5451    | NAC Card (addr)  | 2   | step_5   ||
| | 4007-9812    | Printer Card     | 6   | child    ||
| | ...          | ...              | ... | ...      ||
| +--------------------------------------------------+|
+-----------------------------------------------------+
```

The main panel section is visually distinguished (badge, highlight, or label).

### API Response Structure

The panel selection results endpoint should return groups when multi-panel-group mode was used:

```json
{
  "panel_supported": true,
  "is_multi_group": true,
  "panel_groups": [
    {
      "id": "uuid",
      "boq_description": "2 Loop fire alarm control panel",
      "loop_count": 2,
      "quantity": 1,
      "panel_type": "4007",
      "panel_label": "4007-ES",
      "is_main": false,
      "products": [
        {"product_code": "4007-9101", "product_name": "...", "quantity": 1, "source": "base_unit", "reason": "..."}
      ]
    },
    {
      "id": "uuid",
      "boq_description": "12 Loop Fire Alarm Control Panel",
      "loop_count": 12,
      "quantity": 6,
      "panel_type": "4100ES",
      "panel_label": "4100ES",
      "is_main": true,
      "products": [...]
    }
  ],
  "gate_result": {...},
  "message": "Multi-panel configuration complete. 4 panel groups configured."
}
```

When `is_multi_group` is false or absent, the existing flat `products` array is returned (backward compatible).

---

## Files Modified/Created

| Action | File | Changes |
|--------|------|---------|
| CREATED | `backend/alembic/versions/025_create_panel_groups.py` | Migration: `panel_groups` table + `panel_group_id` on `panel_selections` |
| CREATED | `backend/alembic/versions/029_widen_answer_column.py` | Migration: `analysis_answers.answer` from `VARCHAR(10)` to `TEXT` (Q21 JSON array is too long for 10 chars) |
| EDITED | `backend/app/modules/analysis/models.py` | `answer` column: `String(10)` → `Text` |
| EDITED | `backend/app/modules/panel_selection/service.py` | `SYSTEM_PROMPT`: Q21 instructions updated for per-item JSON array output |
| EDITED | `backend/app/modules/panel_selection/service.py` | New functions: `_parse_q21_loop_items()`, `_derive_max_loop_count()` |
| EDITED | `backend/app/modules/panel_selection/service.py` | `run()`: Q21 parsing uses new parsers, multi-group block uses LLM primary + regex fallback |
| EDITED | `backend/app/modules/panel_selection/service.py` | Renamed `_detect_panel_groups()` → `_detect_panel_groups_regex()` (kept as fallback) |
| EDITED | `backend/app/modules/panel_selection/service.py` | `_run_multi_group()`, `_build_4007_4010_main_products()`, `_store_panel_groups()` — unchanged, already implemented |
| EDITED | `backend/seeds/seed_4007_panel_questions.py` | Q21 question text updated + `update_q21()` function added |

---

## Edge Cases

1. **All panels same loop count (e.g. "4 Loop panel qty 5" and "4 Loop panel qty 3"):** These are the same type. `panel_groups` is NOT returned (or merged into one group). Existing single-panel system handles it — treated as 8 panels of the same type.

2. **Some panels mention loops, some don't (e.g. "Fire Alarm Panel qty 2" and "4 Loop Panel qty 3"):** The ones without loops default to the existing devices_per_panel logic for their type. Alternatively, treat the loop-less panel as a separate group and use the existing Q21/devices logic for it. (Implementation decision — recommend treating loop-less panels as a separate group that falls through to existing logic.)

3. **Only one panel line with loops (e.g. "4 Loop panel qty 10"):** Single group, NOT multi-panel-group mode. Existing system handles it with Q21 = 4.

4. **Re-running panel selection:** Deletes old `panel_groups` and `panel_selections` rows, re-creates from scratch (existing delete-then-insert pattern).

5. **Speakers/telephone added after initial run:** If Q2 or Q3 changes to Yes on re-run, multi-panel-group mode deactivates and all panels become 4100ES via existing path.

6. **MX + Addressable blocking:** In multi-panel-group mode, since each group picks its own panel type, the MX + Addressable block only matters for groups that resolve to 4010. If a group would be 4010 but protocol=MX and notification=addressable, that group should be flagged or upgraded. (Follow existing gate logic per group.)

---

## Constraints

- Do NOT modify the existing single-panel selection flow — it must remain byte-for-byte identical in behavior
- Do NOT change `PANEL_CONFIGS` dictionary
- Do NOT change the 4100ES 17-step product builder (except NAC card and loop card quantity calculations — see `loop_card_count_from_q21_loops.md`)
- Do NOT change the 4007/4010 product builder
- Do NOT change device selection in any way
- Do NOT change the `selectables` table or seed data
- Do NOT change any other module (BOQ extraction, spec analysis protocol logic, etc.)
- The `panel_groups` table and `panel_group_id` column are the only DB schema additions
- When `panel_groups` is empty or not applicable, the system behaves exactly as before — no regressions
- Existing API response format is preserved for single-panel mode (backward compatible)
- Printer + workstation logic remains exactly as-is (applied to main panel only)
- Deferred repeater resolution remains exactly as-is (resolves for main panel type)

---

## Example Walkthrough

### Input BOQ:

| S.No | Description | Qty |
|------|------------|-----|
| 1 | Graphics Work station | 1 |
| 2 | Addressable Smoke Detector | 3,000 |
| 3 | Addressable Heat Detector | 410 |
| 4 | Addressable Horn | 38 |
| 5 | Addressable Manual Pull Station Break Glass Type | 38 |
| 6 | Addressable Horn Flasher | 22 |
| 7 | 2 Loop fire alarm control panel | 1 |
| 8 | Fire Alarm Control Panel 4 Loop | 5 |
| 9 | Fire Alarm Control Panel 6 Loop | 16 |
| 10 | 12 Loop Fire Alarm Control Panel | 6 |

### Step-by-step:

1. **Panel groups extracted:** 4 groups with different loop counts (2, 4, 6, 12) --> multi-panel-group mode activates

2. **Q2 (speakers)?** No horns/flashers don't count as speakers. Q2 = No
   **Q3 (telephone)?** No telephone items in BOQ. Q3 = No
   --> Both No, proceed with multi-panel-group logic

3. **Per-group panel type (by loops):**
   - 2 loops, qty 1 --> **4007**
   - 4 loops, qty 5 --> **4010** (1-bay)
   - 6 loops, qty 16 --> **4010** (2-bay)
   - 12 loops, qty 6 --> **4100ES**

4. **Main panel:** 4100ES has highest priority --> 12-loop group (qty 6) is main panel

5. **Non-main groups get base unit only:**
   - 4007 group: base unit x 1
   - 4010_1bay group: base unit x 5
   - 4010_2bay group: base unit x 16

6. **Main panel (4100ES, qty 6) gets full product build:**
   - Controller, loop cards, NAC cards (ceil(12/6) = 2 cards), printer (if Q14=Yes and no workstation — but workstation exists so no printer card), BMS (if Q204=Yes), networking (project network_type), PSUs, enclosures, etc.
   - All quantities multiplied by 6 (num_panels)

7. **NAC cards:** ceil(12/6) = 2 cards of 4100-5451 (addressable) or 4100-5450 (conventional)

8. **Deferred repeaters:** Resolved for 4100ES series (main panel type)

### Result: 4 sections in the output, each with their panel group's BOQ item and products.
