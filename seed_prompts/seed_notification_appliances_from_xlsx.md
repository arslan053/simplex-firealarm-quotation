# Seed: Notification Appliance Selectables from Excel (notifications_with_subcategories.xlsx)

You are working inside an existing monorepo that already contains:
- A **global `products` table** with `code` (TEXT, UNIQUE) as the product identifier
- A **global `selectables` table** with `boq_match_phrases` (TEXT[]), `description` (TEXT), `specification_hints` (TEXT), `category` (selectable_category_enum), `selection_type` (selection_type_enum), `priority` (TEXT), `subcategory` (TEXT)
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

## Goal

Create a standalone seed script that reads **`./notifications_with_subcategories.xlsx`** and inserts notification appliance selectables into the `selectables` table, with proper links to the `products` table via `selectable_products`.

---

## Input File

Path: `./notifications_with_subcategories.xlsx`

### File Structure

The Excel file has 9 columns:

| Column A | Column B | Column C | Column D | Column E | Column F | Column G | Column H | Column I |
|---|---|---|---|---|---|---|---|---|
| S. No | Part Numbers | Aliases | Description.1 | Colour | Mounting Type | Final Description | Priority | Subcategory |

### Column Mapping

- **Column A (index 0)**: S.No — row serial number OR section header text (used for category detection)
- **Column B (index 1)**: Part Numbers — one or more product codes (may contain multiple codes separated by commas, `and`, `&`, newlines)
- **Column C (index 2)**: Aliases — comma-separated synonyms/phrases used for BOQ matching → stored as `boq_match_phrases` (TEXT[])
- **Column D (index 3)**: Description.1 — not directly stored
- **Column E (index 4)**: Colour — not directly stored
- **Column F (index 5)**: Mounting Type — not directly stored
- **Column G (index 6)**: Final Description — the display description → stored as `description` (TEXT)
- **Column H (index 7)**: Priority — priority level (e.g. "High") → stored as `priority` (TEXT)
- **Column I (index 8)**: Subcategory — device subcategory (e.g. "flasher", "horn", "horn_flasher", "speaker", "speaker_flasher") → stored as `subcategory` (TEXT)
- **`specification_hints`** = always NULL for notification devices (no specs in this file)

### Section Headers Determine Category

The file contains **two sections** separated by header rows in Column A:

1. **`NON-ADDRESSABLE NOTIFICATION APPLIANCES`** — appears as a merged row near the top.
   All data rows below this header (until the next header) belong to category: **`non_addressable_notification_device`**

2. **`ADDRESSABLE NOTIFICATION APPLIANCES`** — appears as a merged row mid-file.
   All data rows below this header (until the end) belong to category: **`addressable_notification_device`**

### How to Detect Section Headers

- When Column A contains a string like `NON-ADDRESSABLE NOTIFICATION APPLIANCES` or `ADDRESSABLE NOTIFICATION APPLIANCES` (case-insensitive match), treat it as a section header.
- Check for "non-addressable" first (more specific) before "addressable".
- Switch the current category accordingly.
- Do NOT create a selectable from header rows.

---

## Row Processing Rules

For each data row:

1. Read **Part Numbers** from Column B — may contain one or more product codes
2. Read **Aliases** from Column C — comma-separated synonyms for BOQ matching
3. Read **Final Description** from Column G — display description
4. Read **Priority** from Column H — priority level (or NULL)
5. Read **Subcategory** from Column I — device subcategory (or NULL)
6. Determine **category** based on which section header the row falls under

### Selection Type

- If a row has **1 product code** → `selection_type = 'single'`
- If a row has **multiple product codes** → `selection_type = 'combo'`

### Specification Hints

- **No specification hints** — this file does not contain `Specs:` lines → `specification_hints = NULL` for all records

### Skip Rules

- Skip rows where both Part Number and Aliases are empty
- Skip section header rows
- Skip fully empty rows
- **Skip rows where ANY product code is missing from the `products` table** (see Product Matching below)

---

## Aliases Extraction (Column C → boq_match_phrases)

Column C contains comma-separated synonyms/aliases used for BOQ matching.

Example Column C value:
```
Wall-- Flasher , Stobe, Visual,Strobe light, - Multi Candella --Red
```

### Parsing Steps

1. Take the Column C value as-is
2. Split by `,`
3. Trim each element
4. Remove empty strings
5. Remove trailing periods
6. Deduplicate (preserving order)
7. Store as TEXT[] in the `boq_match_phrases` column

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
- **Collect the skipped row** for the final report (row number, missing codes, all codes, description, category)

### Final Skipped Selectables Report

At the end of execution, print a clearly formatted list of all selectables that were **skipped because one or more product codes were not found** in the `products` table. For each, show:
- Excel row number
- All Part Numbers from that row
- Which specific codes were missing
- Aliases (Column C value)
- Final Description (Column G value)
- Category (which section it belonged to)

This list allows the user to add the missing products and re-run the seed.

---

## Script Behavior

Create a SINGLE standalone seed script file.

Suggested path:
- `./backend/seeds/seed_notification_appliance_selectables.py`

The script must:

1) Accept Excel path as CLI arg
   Default: `../../notifications_with_subcategories.xlsx` (relative to script location — the file in repo root)

2) Read Excel reliably
   Use: `pandas` + `openpyxl` (consistent with existing seed scripts)

3) Detect section headers to assign category

4) Parse row by row following the rules above

5) For each row with valid Part Numbers and Aliases:
   - Extract all product codes from Column B
   - Look up ALL codes in the `products` table
   - If ALL found → create the selectable record + all `selectable_products` junction records
   - If ANY missing → skip the entire selectable, collect for the skipped report

6) Use a transaction for all inserts

### Idempotency

Before inserting new records:
- Delete all existing selectables with `category IN ('non_addressable_notification_device', 'addressable_notification_device')`
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
   - `boq_match_phrases` arrays properly populated
   - All `specification_hints` are NULL
   - `selection_type` values are correct (`single` or `combo`)
   - `priority` and `subcategory` properly populated where present
   - `selectable_products` junction records created for ALL products of each selectable
   - No selectables exist with missing product links (they should have been skipped)
   - Rerun is idempotent

---

## Final Output Required

At the end, print or show:

### Seed Summary
- Total Excel rows read
- Rows skipped (empty / header rows)
- Non-addressable selectables created
- Addressable selectables created
- Total selectables created
- Total `selectable_products` links created
- Total selectables skipped (due to missing products)

### Skipped Selectables Report
A complete list of every selectable that was **skipped** because one or more product codes were not found in the `products` table. For each entry show:
- Row number
- All Part Numbers
- Missing codes (which specific codes were not found)
- Aliases
- Final Description
- Category

### Missing Products List
A deduplicated list of ALL unique product codes that were not found in the `products` table (across all skipped selectables). This gives a quick overview of which products need to be added to the products table before re-running the seed.

---

## Deliverables

1) One standalone seed script file that:
   - Reads `./notifications_with_subcategories.xlsx`
   - Detects section headers to assign correct category
   - Extracts aliases from Column C → `boq_match_phrases`
   - Extracts final description from Column G → `description`
   - Extracts priority from Column H → `priority`
   - Extracts subcategory from Column I → `subcategory`
   - Looks up ALL Part Numbers for each row in the `products` table
   - Only creates selectables when ALL product codes exist in the products table
   - Skips the entire selectable if ANY product code is missing
   - Links ALL products via junction table for created selectables
   - Reports all skipped selectables clearly at the end

2) Proof of running:
   - Seed logs / summary output
   - Skipped selectables report

---

## Constraints

- Do NOT change any existing project/spec/boq modules.
- Do NOT modify the products table.
- This is a separate seed utility only.
- Keep diffs minimal and consistent with repo patterns.
- Follow the repo's DB connection + migration conventions.
