# Seed: Annunciator & Subpanel Selectables from Excel (Annunciators-Subpanels.xlsx)

You are working inside an existing monorepo that already contains:
- A **global `products` table** with `code` (TEXT, UNIQUE) as the product identifier
- A **global `selectables` table** with `boq_match_phrases` (TEXT[]), `description` (TEXT), `specification_hints` (TEXT), `priority` (TEXT), `subcategory` (TEXT), `category` (selectable_category_enum), `selection_type` (selection_type_enum)
- A **`selectable_products`** junction table linking selectables to products (many-to-many)
- Existing seed scripts under `./backend/seeds/`

IMPORTANT:
- First read and follow `./prompts/workflow_orchestration.md` as mandatory operating rules if it exists in the repo.
- Read `./prompts/selectables_module_prompt.md` to understand the full selectables data model.
- This task is **independent** from the main project modules.
- Do NOT modify any existing project/spec/boq logic.
- Do NOT modify the products table.
- Keep changes minimal, professional, and consistent with repo seed script patterns.
- Follow the repo's DB connection conventions (see `./backend/seeds/seed_global_products.py` as reference).

---

## Background: What Are Annunciators & Subpanels?

These are **accessories and peripheral devices** that connect to the main fire alarm control panel:

- **Graphics Workstations** — PC-based monitoring stations with software and network cards (wired, fiber, or IP)
- **Repeater / Annunciator Panels** — LCD remote panels that mirror the main panel (model-specific: 4100ES, 4010, 4007)
- **Mimic / Override Panels** — AHU override and elevator control panels with switches

Each selectable in this file is a **combo** (multiple product codes bundled together), and some have specification hints or notes that guide selection.

---

## Pre-requisite: New Enum Value

The current `selectable_category_enum` has 5 values:
- `mx_detection_device`
- `idnet_detection_device`
- `addressable_notification_device`
- `non_addressable_notification_device`
- `conventional_device`

**Before running the seed script**, a new Alembic migration must add `'annunciator_subpanel'` to the enum:

```sql
ALTER TYPE selectable_category_enum ADD VALUE IF NOT EXISTS 'annunciator_subpanel';
```

Create this migration as the next sequential migration file in `backend/alembic/versions/`. Follow the existing pattern of raw SQL for enum operations (do NOT use `sa.Enum.create()`).

---

## Source File

**Path:** `./Annunciators-Subpanels.xlsx`

---

## Goal

Create a standalone seed script that reads **`./Annunciators-Subpanels.xlsx`** and inserts annunciator/subpanel selectables into the `selectables` table, with proper many-to-many links to the `products` table via `selectable_products`.

---

## Input File

### File Structure

The Excel file has **6 columns**:

| Column A | Column B | Column C | Column D | Column E | Column F |
|---|---|---|---|---|---|
| S. No | Part Numbers | aliases | Description | Sub category | Priority |

### Column Mapping

- **Column A (index 0)**: S.No — row serial number (integer). Use for logging only.
- **Column B (index 1)**: Part Numbers — one or more product codes separated by **newlines** (`\n`). Each line is a separate product code.
- **Column C (index 2)**: aliases — comma-separated synonyms / BOQ match phrases, **possibly followed by a `Specs :` or `Note :` line** on a new line within the same cell. First line → `boq_match_phrases` (TEXT[]), subsequent Specs/Note lines → `specification_hints` (TEXT).
- **Column D (index 3)**: Description — final display description text → stored as `description` (TEXT).
- **Column E (index 4)**: Sub category — device subcategory (e.g. `work_station`) → stored as `subcategory` (TEXT). May be NaN.
- **Column F (index 5)**: Priority — priority level (e.g. `High`) → stored as `priority` (TEXT). May be NaN.
- **`category`** = always `'annunciator_subpanel'` for all rows.

### Row 0 is the header row — skip it.

### All Data Rows (9 rows total: rows 1–9)

| Row | S.No | Part Numbers | aliases (summary) | Description | Subcategory | Priority |
|---|---|---|---|---|---|---|
| 1 | 1 | `4190-8606`, `4190-9829`, `4190-9822` | Graphics, work station, PC... — Specs: wired networking + no override | Graphics software with network card wired media type with Dell PC | work_station | High |
| 2 | 2 | `4190-8606`, `4190-9829`, `4190-6301`, `4190-6302` | Graphics, work station, PC... — Specs: fiber networking + no override | Graphics software with network card fiber media type with Dell PC | work_station | — |
| 3 | 3 | `4190-8603`, `4190-9829`, `4190-9822` | Graphics, work station, PC... — Specs: wired networking + override | Graphics software with network card wired media type with Dell PC | work_station | — |
| 4 | 4 | `4190-8603`, `4190-9829`, `4190-6301`, `4190-6302` | Graphics, work station, PC... — Specs: fiber networking + override | Graphics software with network card fiber media type with Dell PC | work_station | — |
| 5 | 5 | `4190-8603`, `4190-5050`, `Surguard-V` | Graphics, work station, PC... — Specs: IP networking | Graphics software with Dell PC and DACR | work_station | — |
| 6 | 6 | `4603-9101`, `2975-9206` | Annunciator, Repeator, LCD panel... — Note: 4100ES series | Repeator Panel | — | — |
| 7 | 7 | `4606-9102`, `2975-9206` | Annunciator, Repeator, LCD panel... — Note: 4010ES series | Repeator Panel | — | — |
| 8 | 8 | `4606-9202`, `2975-9461` | Annunciator, Repeator, LCD panel... — Note: 4007ES series | Repeator Panel | — | — |
| 9 | 9 | `4100-7402`, `4100-7403`, `4100-7404` | Mimic, Override, AHU Override Panel, Elevator Control Panel | Mimic Panel with Override switches | — | — |

---

## aliases Column Parsing (Column C) — CRITICAL

Column C cells contain **multi-line content**. The first line holds comma-separated BOQ match phrases. Subsequent lines (if any) hold `Specs :` or `Note :` directives.

### Parsing Steps

1. Split the cell value by `\n` (newline)
2. Classify each line:
   - If line starts with `Specs` (case-insensitive) followed by `:` → it is a **specification hint**
   - If line starts with `Note` (case-insensitive) followed by `:` → it is a **specification hint** (treat same as Specs)
   - Otherwise → it is the **BOQ match phrases** line
3. For BOQ match phrases lines:
   - Split by `,`
   - Trim each element
   - Remove empty strings
   - Remove trailing periods
   - Deduplicate (preserve order)
   - Store as TEXT[] in `boq_match_phrases`
4. For specification hint lines:
   - Strip the `Specs :` or `Note :` prefix (including any surrounding whitespace)
   - Prepend: `"Refer to project specifications for: "`
   - Store in `specification_hints` (TEXT)
   - If multiple hint lines exist, join with ` | ` separator

### Examples

**Row 1 — Cell C:**
```
Graphics, work station, PC, Software, computer
Specs : If networking is wired / copper type and ovverride is not mentioned in specs
```
- `boq_match_phrases`: `["Graphics", "work station", "PC", "Software", "computer"]`
- `specification_hints`: `"Refer to project specifications for: If networking is wired / copper type and ovverride is not mentioned in specs"`

**Row 6 — Cell C:**
```
Annunciator, Repeator, LCD panel, FARP, Fire Alarm repeater panel
Note : If panel selected is from 4100es series
```
- `boq_match_phrases`: `["Annunciator", "Repeator", "LCD panel", "FARP", "Fire Alarm repeater panel"]`
- `specification_hints`: `"Refer to project specifications for: If panel selected is from 4100es series"`

---

## Product Code Extraction (from Column B — `Part Numbers`)

Column B contains product codes separated by **newlines** (`\n`). Same pattern as `Conventional devices.xlsx`.

### Parsing Steps

1. Convert cell to string
2. Split by newline (`\n`)
3. Trim each line
4. Remove empty lines
5. Each non-empty line is one product code

### Selection Type

Based on the number of codes **extracted** (not found in DB):
- 1 code → `single`
- 2+ codes → `combo`

**In this file, all 9 rows have 2+ codes, so all are `combo`.**

---

## Product Matching (CRITICAL)

Before creating a selectable, **ALL product codes for that row must exist** in the `products` table.

### Pre-check: Verify ALL product codes exist

For each data row:
1. Extract all product codes from Column B
2. Look up EACH code in the `products` table
3. If **ALL codes are found** → proceed to create the selectable + junction records
4. If **ANY code is NOT found** → **SKIP the entire selectable** (do NOT insert it)

### When ALL products are found:
- Create the selectable record
- Create `selectable_products` junction records linking the selectable to ALL matched products

### When ANY product is NOT found:
- **Do NOT create the selectable record**
- **Do NOT create any junction records**
- **Collect the skipped row** for the final report (row number, missing codes, all codes, description)

---

## Script Behavior

Create a SINGLE standalone seed script file.

Path: `./backend/seeds/seed_annunciator_subpanel_selectables.py`

The script must:

1) Accept Excel path as CLI arg
   Default: `../../Annunciators-Subpanels.xlsx` (relative to script location — the file in repo root)

2) Read Excel reliably
   Use: `pandas` + `openpyxl` (consistent with existing seed scripts)

3) Parse row by row following the rules above

4) For each valid row:
   - Extract all product codes from Column B
   - Look up ALL codes in the `products` table
   - If ALL found → create the selectable record + all `selectable_products` junction records
   - If ANY missing → skip the entire selectable, collect for the skipped report

5) Use a transaction for all inserts

### Idempotency

Before inserting new records:
- Clear FK references from `boq_device_selections` pointing to annunciator_subpanel selectables
- Delete all existing selectables with `category = 'annunciator_subpanel'`
- This cascades to delete related `selectable_products` records (via ON DELETE CASCADE)
- Then insert fresh from the file

This ensures rerunning the script produces the same result without duplicates.

### Skip Rules

- Skip row 0 (header)
- Skip rows where both Column B (Part Numbers) AND Column C (aliases) are empty/NaN
- Skip fully empty rows
- **Skip rows where ANY product code is missing from the `products` table**

---

## LLM Device Selection Integration

After seeding annunciator/subpanel selectables, update the **device selection LLM service** (`backend/app/modules/device_selection/service.py`) so the LLM knows about this new category.

### Catalog Query — No Change Needed

The current query uses `WHERE s.category != :exclude_cat` (excluding the opposite addressable protocol). Annunciator/subpanel selectables will **never be excluded** because:
- MX protocol → excludes `idnet_detection_device` → `annunciator_subpanel` NOT excluded
- IDNET protocol → excludes `mx_detection_device` → `annunciator_subpanel` NOT excluded

So **no query change is needed**.

### LLM System Prompt Update

Add a new rule to the SYSTEM_PROMPT:

> **14. Annunciators & Subpanels**: The catalog contains annunciator and subpanel selectables with category `"annunciator_subpanel"`. These include graphics workstations (PC + software + network card), repeater/annunciator LCD panels, and mimic/override panels. Key matching rules:
>
> (a) **Graphics Workstations** — When a BOQ item mentions "graphics", "workstation", "PC", "software", or "computer" for fire alarm monitoring, match to an annunciator_subpanel selectable. Use the `specification_hints` to disambiguate: check whether the project spec mentions wired/copper or fiber networking, and whether override functionality is mentioned. Pick the variant that matches the spec conditions.
>
> (b) **Repeater / Annunciator Panels** — When a BOQ item mentions "annunciator", "repeater", or "LCD panel", match to an annunciator_subpanel selectable. Use the `specification_hints` to pick the correct panel-series variant (4100ES, 4010, or 4007) based on which main panel the project uses. The repeater MUST match the main panel series.
>
> (c) **Mimic / Override Panels** — When a BOQ item mentions "mimic", "override", "AHU override", or "elevator control panel", match to the mimic panel selectable.

---

## Run + Verify (Mandatory)

After implementation, you MUST:

1) Create the migration to add `'annunciator_subpanel'` to the enum
2) Run `alembic upgrade head`
3) Run the seed script
4) Query DB to confirm:
   - Selectables created with `category = 'annunciator_subpanel'`
   - `boq_match_phrases` arrays properly populated from Column C (first line only, no Specs/Note content)
   - `specification_hints` populated where Specs/Note lines exist
   - `description` column populated from Column D
   - `subcategory` populated where present (e.g. `work_station`)
   - `priority` populated where present (e.g. `High`)
   - `selectable_products` junction records created for ALL products of each selectable
   - No selectables exist with missing product links (they should have been skipped)
   - All `selection_type` values are `combo`
   - No duplicate selectables
   - Rerun is idempotent

---

## Final Output Required

At the end, print or show:

### Seed Summary
- Total Excel rows read
- Rows skipped (empty / header / missing products)
- Annunciator/subpanel selectables created
- Combo selectables count (should be all of them)
- Total `selectable_products` links created
- Total selectables skipped (due to missing products)

### Skipped Selectables Report
A complete list of every selectable that was **skipped** because one or more product codes were not found in the `products` table. For each entry show:
- S. No (row number)
- All Part Numbers from that row
- Which specific codes were missing
- Description
- Subcategory (if any)

### Missing Products List
A deduplicated list of ALL unique product codes that were not found in the `products` table (across all skipped selectables). This gives a quick overview of which products need to be added to the products table before re-running the seed.

### Sample Records
Show all selectables with:
- category
- selection_type
- boq_match_phrases
- specification_hints
- description
- subcategory
- priority
- linked product codes

---

## Deliverables

1) One Alembic migration file that adds `'annunciator_subpanel'` to `selectable_category_enum`
2) One standalone seed script file (`./backend/seeds/seed_annunciator_subpanel_selectables.py`) that:
   - Reads `./Annunciators-Subpanels.xlsx`
   - Parses aliases (Column C) into `boq_match_phrases` + `specification_hints` (handling Specs/Note lines)
   - Extracts `description` from Column D
   - Extracts `subcategory` from Column E
   - Extracts `priority` from Column F
   - Extracts product codes from Column B (newline-separated)
   - Creates selectables with `category = 'annunciator_subpanel'`
   - Only creates selectables when ALL product codes exist in the products table
   - Skips the entire selectable if ANY product code is missing
   - Links ALL products via junction table for created selectables
   - Reports all skipped selectables and missing product codes clearly at the end
3) Updates to `backend/app/modules/device_selection/service.py`:
   - Add annunciator/subpanel rules (rule 14) to the LLM SYSTEM_PROMPT
4) Proof of running:
   - Seed logs / summary output
   - Sample query output
   - Skipped selectables report

---

## Constraints

- Do NOT change any existing project/spec/boq modules (except the device selection service updates).
- Do NOT modify the products table.
- Do NOT modify existing seed scripts for detection, notification, or conventional devices.
- Keep diffs minimal and consistent with repo patterns.
- Follow the repo's DB connection + migration conventions.
- For Postgres enum changes: use raw SQL in Alembic migrations (not `sa.Enum`).
