# Seed: Detection Device Selectables from Excel (detetction devices.xlsx)

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

## Source File

**Pick this file from the project root folder:** `./detetction devices.xlsx`

---

## Goal

Create a standalone seed script that reads **`./detetction devices.xlsx`** and inserts detection device selectables into the `selectables` table, with proper many-to-many links to the `products` table via `selectable_products`.

---

## Input File

Path: `./detetction devices.xlsx`

### File Structure

The Excel file has 4 columns:

| Column A | Column B | Column C | Column D |
|---|---|---|---|
| Designation/Model No (IDNet) | aliases | MX model No/Description | Description |

### Column Mapping

- **Column A (index 0)**: IDNet product codes — may contain single or multiple codes separated by `and`, `with`, commas, etc. → determines `selectable_products` links for `idnet_detection_device`
- **Column B (index 1)**: aliases — comma-separated BOQ match synonyms, optionally followed by specification hints on a new line starting with `Specs:` or `Specs :`. First line → `boq_match_phrases` (TEXT[]), Specs lines → `specification_hints` (TEXT). **Note**: The Excel header says `Description ` (with trailing space) but this column contains aliases/BOQ phrases, NOT the final description.
- **Column C (index 2)**: MX product codes — same messy format as IDNet → determines `selectable_products` links for `mx_detection_device`
- **Column D (index 3)**: Description — the final display description text → stored as `description` (TEXT)
- **`priority`** = always `NULL` (no priority column in this file)
- **`subcategory`** = always `NULL` (no subcategory column in this file)

---

## Row Processing Rules

For each row in the Excel file:

1. Read the aliases cell (Column B) — for BOQ match phrases + spec hints
2. Read the Description cell (Column D) — for the final display description
3. Read the IDNet cell (Column A) — for IDNet product codes
4. Read the MX cell (Column C) — for MX product codes

Then:
- If the **IDNet cell** has valid product code(s) AND all codes exist in products table → create one selectable with `category = idnet_detection_device`
- If the **MX cell** has valid product code(s) AND all codes exist in products table → create one selectable with `category = mx_detection_device`
- Both selectables share the **same boq_match_phrases, description, and specification hints** extracted from Columns B and D

This means:
- One Excel row can create **two** selectable records (one IDNet, one MX)
- Or **one** record if only one side has product codes (or the other side has missing products)
- Or **zero** records if both sides are empty or have missing products

### Skip Rules

If aliases is empty and both side cells are empty:
- Skip row entirely

If aliases exists but neither side yields any valid product code:
- Skip row and log warning

---

## Aliases and boq_match_phrases Extraction (Column B)

Column B contains two parts separated by a newline (`\n`):

1. **Aliases** — comma-separated synonyms (before the `Specs:` line)
2. **Specification hints** — optional, after `Specs:` or `Specs :`

### Parsing Steps

1. Split the cell content by `\n`
2. Find the line that starts with `Specs:` or `Specs :` (case-insensitive match on the word `Specs`)
3. Everything before that line = aliases text
4. The Specs line content (after the colon) = specification hints

### boq_match_phrases Array

- Split the aliases text by `,`
- Trim each element
- Remove empty strings
- Remove trailing periods from elements
- Deduplicate (preserve order)
- Store as TEXT[] in the `boq_match_phrases` column

### description Column (Column D)

- Take the Column D value as-is
- Store in the `description` column
- This is the final display text shown when this selectable is matched to a BOQ item

### Specification Hints

- If a `Specs:` line exists in Column B:
  - Extract the content after the colon — keep it **exactly as-is** from the file (no cleanup, no rewording)
  - Replace the prefix `Specs` with `Refer to project specifications for`
  - Store the full resulting string in the `specification_hints` column

- If no `Specs:` line exists:
  - Store NULL in `specification_hints`

Example:
- Cell B: `Duct Detector, Duct Smoke Detector\nSpecs : No relay duct detector, No HVAC Shutdown`
- Cell D: `Addressable Duct Detector`
- boq_match_phrases: `["Duct Detector", "Duct Smoke Detector"]`
- description: `"Addressable Duct Detector"`
- Specification hints: `"Refer to project specifications for: No relay duct detector, No HVAC Shutdown"`

---

## Product Code Extraction Rules (CRITICAL)

Product code cells (Columns A and C) are messy and may contain:
- Multiple product codes separated by `and`
- Commas
- Ampersands
- New lines
- `with`
- Extra spaces
- Notes in brackets
- Descriptive words after the code

### Examples

- `4098-5266 and 4098-5260 and 2098-9808`

- `2099-9139 and 2975-9211 (wp box) and 4090-5201(MM)`
  - Ignore `(wp box)` and `(MM)` and capture only:
    - `2099-9139`
    - `2975-9211`
    - `4090-5201`

- `4098-5214 with 4098-5252 and STS-2.5 sampling tube`
  - Capture:
    - `4098-5214`
    - `4098-5252`
    - `STS-2.5`
  - Ignore `sampling tube`

- `VESDA VEP-A00-P`
  - Capture:
    - `VEP-A00-P`
  - Ignore `VESDA`

### Required Extraction Behavior

1) Convert cell to string
2) Trim whitespace
3) Remove bracketed text like `(wp box)` `(MM)`
4) Normalize separators:
   - `and`
   - `with`
   - `,`
   - `;`
   - `&`
   - `/`
   - `|`
   - newline
5) Extract valid code-like tokens only
6) Ignore explanatory trailing words
7) Deduplicate codes within a single cell
8) Preserve stable order where practical

### Accepted Code Patterns

The parser must capture codes like:
- `4098-5266`
- `2098-9808`
- `STS-2.5`
- `VEP-A00-P`

A regex-based approach is fine, for example matching tokens like:
- Uppercase/digit groups joined by `-`
- Optional dots within later segments

Do not store filler words.

---

## Product Matching (CRITICAL)

Before creating a selectable, **ALL product codes for that side (IDNet or MX) must exist** in the `products` table.

### Pre-check: Verify ALL product codes exist

For each side (IDNet / MX) of each data row:
1. Extract all product codes from the cell
2. Look up EACH code in the `products` table
3. If **ALL codes are found** → proceed to create the selectable + junction records for that side
4. If **ANY code is NOT found** → **SKIP that side's selectable** (do NOT insert it)

**Important**: Each side is checked independently. If IDNet has missing codes but MX is complete, only the MX selectable is created (and vice versa).

### When ALL products are found for a side:
- Create the selectable record
- Create `selectable_products` junction records linking the selectable to ALL matched products

### When ANY product is NOT found for a side:
- **Do NOT create the selectable record** for that side
- **Do NOT create any junction records** for that side
- **Collect the skipped entry** for the final report (row number, side, missing codes, all codes, description)

### Selection Type

Set `selection_type` based on the number of product codes **extracted** from the cell (not the number found in DB):
- 1 code extracted → `single`
- 2+ codes extracted → `combo`

---

## Category Assignment

Based on which column the product codes come from:

| Source Column | Category |
|---|---|
| Column A (IDNet) | `idnet_detection_device` |
| Column C (MX) | `mx_detection_device` |

---

## Script Behavior

Create a SINGLE standalone seed script file.

Suggested path (pick the most consistent with repo):
- `./backend/seeds/seed_detection_device_selectables.py`

The script must:

1) Accept Excel path as CLI arg
   Default: `../../detetction devices.xlsx` (relative to script location — the file in repo root)

2) Read Excel reliably
   Use: `pandas` + `openpyxl` (consistent with existing seed scripts)

3) Detect or confirm columns for:
   - IDNet (Column A)
   - aliases (Column B)
   - MX (Column C)
   - Description (Column D)

4) Parse row by row following the rules above

5) For each valid row, create 0-2 selectable records and their product links

6) Use a transaction for all inserts

### Idempotency

Before inserting new records:
- Clear FK references from `boq_device_selections` pointing to detection device selectables
- Delete all existing selectables with `category IN ('mx_detection_device', 'idnet_detection_device')`
- This cascades to delete related `selectable_products` records (via ON DELETE CASCADE)
- Then insert fresh from the file

This ensures rerunning the script produces the same result without duplicates.

---

## Run + Verify (Mandatory)

After implementation, you MUST:

1) Ensure the selectables migration has been applied (tables + enums exist)
2) Run the seed script
3) Query DB to confirm:
   - Selectables created with correct categories
   - `boq_match_phrases` arrays properly populated from Column B (aliases)
   - `description` column populated from Column D
   - `specification_hints` stored with renamed prefix where applicable
   - `priority` is NULL for all records
   - `subcategory` is NULL for all records
   - `selectable_products` junction records created for ALL products of each selectable
   - No selectables exist with missing product links (they should have been skipped)
   - Selection types correctly set (single vs combo)
   - No duplicate selectables
   - Rerun is idempotent

---

## Final Output Required

At the end, print or show:

### Seed Summary
- Total Excel rows read
- Rows skipped (empty / missing products)
- IDNet selectables created
- MX selectables created
- Total `selectable_products` links created
- Total selectables skipped (due to missing products)

### Skipped Selectables Report
A complete list of every selectable that was **skipped** because one or more product codes were not found in the `products` table. For each entry show:
- Row number
- Side (IDNet or MX)
- All Part Numbers from that side
- Which specific codes were missing
- Description (Column D)

### Missing Products List
A deduplicated list of ALL unique product codes that were not found in the `products` table (across all skipped selectables). This gives a quick overview of which products need to be added to the products table before re-running the seed.

### Sample Records
Show 3-5 sample selectables with:
- category
- selection_type
- boq_match_phrases (first 3)
- description
- specification_hints (if any)
- linked product codes

---

## Deliverables

1) One standalone seed script file that:
   - Reads `./detetction devices.xlsx`
   - Extracts `boq_match_phrases` from Column B (aliases) — comma-separated, with Specs parsing
   - Extracts `description` from Column D
   - Extracts `specification_hints` from Specs lines in Column B
   - Extracts product codes from IDNet (Column A) and MX (Column C)
   - Creates selectables with proper category and selection_type
   - Only creates selectables when ALL product codes for that side exist in the products table
   - Skips the selectable for that side if ANY product code is missing
   - Links ALL products via junction table for created selectables
   - Reports all skipped selectables and missing product codes clearly at the end

2) Proof of running:
   - Seed logs / summary output
   - Sample query output
   - Skipped selectables report

---

## Constraints

- Do NOT change any existing project/spec/boq modules.
- Do NOT modify the products table.
- This is a separate seed utility only.
- Keep diffs minimal and consistent with repo patterns.
- Follow the repo's DB connection + migration conventions.
