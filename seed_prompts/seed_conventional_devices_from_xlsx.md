# Seed: Conventional Device Selectables from Excel (Conventional devices.xlsx)

You are working inside an existing monorepo that already contains:
- A **global `products` table** with `code` (TEXT, UNIQUE) as the product identifier
- A **global `selectables` table** with `boq_match_phrases` (TEXT[]), `description` (TEXT), `specification_hints` (TEXT), `priority` (TEXT), `category` (selectable_category_enum), `selection_type` (selection_type_enum)
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

## Background: Device Taxonomy

The fire protection system has two major device families:

```
Devices
├── Addressable (one protocol per project: either IDNET or MX)
│   ├── Detection Devices
│   │   ├── idnet_detection_device   ← existing category
│   │   └── mx_detection_device      ← existing category
│   └── Notification Appliances
│       ├── addressable_notification_device        ← existing category
│       └── non_addressable_notification_device    ← existing category
│
└── Conventional (non-addressable, protocol-independent)
    └── conventional_device   ← NEW category (this task)
```

### Key rules about how conventional devices coexist with addressable devices:

1. **A project can have BOTH addressable AND conventional devices at the same time.** They are not mutually exclusive.
2. **Even within detection devices**, a project can have addressable detection devices (IDNET or MX) AND conventional detection devices simultaneously.
3. **Addressable protocol** remains singular per project — either IDNET or MX, never both. But conventional devices sit alongside whichever addressable protocol is chosen.
4. **Conventional devices are always available** in the catalog regardless of the project's addressable protocol (MX or IDNET). They are never filtered out.
5. **Conventional devices cover a broad range** — not just detection. They include detectors, switches, manual pull stations, notification appliances, control panels, suppression components, and more. This is fundamentally different from the IDNET/MX split which only covers detection devices.

---

## Pre-requisite: New Enum Value

The current `selectable_category_enum` has 4 values:
- `mx_detection_device`
- `idnet_detection_device`
- `addressable_notification_device`
- `non_addressable_notification_device`

**Before running the seed script**, a new Alembic migration must add `'conventional_device'` to the enum:

```sql
ALTER TYPE selectable_category_enum ADD VALUE IF NOT EXISTS 'conventional_device';
```

Create this migration as the next sequential migration file in `backend/alembic/versions/`. Follow the existing pattern of raw SQL for enum operations (do NOT use `sa.Enum.create()`).

---

## Source File

**Path:** `./Conventional devices.xlsx`

---

## Goal

Create a standalone seed script that reads **`./Conventional devices.xlsx`** and inserts conventional device selectables into the `selectables` table, with proper many-to-many links to the `products` table via `selectable_products`.

---

## Input File

### File Structure

The Excel file has 4 columns:

| Column A | Column B | Column C | Column D |
|---|---|---|---|
| S. No | Part Numbers | aliases | Description |

- **Column A (`S. No`)**: Sequential row number (integer). Use for logging only.
- **Column B (`Part Numbers`)**: One or more product codes separated by **newlines** (`\n`). Each line is a separate product code.
- **Column C (`aliases`)**: Comma-separated synonyms / BOQ match phrases. These are the terms that might appear in a BOQ description when referring to this device.
- **Column D (`Description`)**: Final display description text. This is the clean, human-readable name for the device.

### Column Mapping to `selectables` Table

| Excel Column | Selectables Column | Notes |
|---|---|---|
| Column C (`aliases`) | `boq_match_phrases` (TEXT[]) | Split by comma, trim, deduplicate |
| Column D (`Description`) | `description` (TEXT) | Store as-is — this is the display text |
| — | `category` | Always `'conventional_device'` for all rows |
| — | `specification_hints` | Always `NULL` (no specs in this file) |
| — | `priority` | Always `NULL` (no priority in this file) |
| Column B (`Part Numbers`) | Determines `selection_type` + `selectable_products` links | See below |

---

## Row Processing Rules

For each row in the Excel file:

1. Read `S. No` from Column A (for logging)
2. Read `Part Numbers` from Column B
3. Read `aliases` from Column C
4. Read `Description` from Column D

### Category Assignment

All rows get: `category = 'conventional_device'`

There is no section-based category switching (unlike notification appliances).

### Skip Rules

- Skip rows where Column B (Part Numbers) AND Column C (aliases) are both empty/NaN
- Skip fully empty rows

---

## boq_match_phrases Extraction (from Column C — `aliases`)

Column C contains comma-separated synonym phrases.

### Parsing Steps

1. Take the Column C value as a string
2. Split by `,`
3. Trim each element
4. Remove empty strings
5. Remove trailing periods from elements
6. Deduplicate (preserve order)
7. Store as TEXT[] in the `boq_match_phrases` column

### Example

- Cell: `Conventional Smoke, Non Addressable Smoke, Conventional Optical, Conventional Photo,`
- Result: `["Conventional Smoke", "Non Addressable Smoke", "Conventional Optical", "Conventional Photo"]`

---

## description Column (from Column D — `Description`)

- Take the Column D value as-is
- Store in the `description` column
- This is the final display text shown when this selectable is matched to a BOQ item

### Example

- Cell: `Conventional Smoke Detector with base`
- Result: `"Conventional Smoke Detector with base"`

---

## Product Code Extraction (from Column B — `Part Numbers`)

Column B contains product codes separated by **newlines** (`\n`). This is simpler than the detection devices file.

### Parsing Steps

1. Convert cell to string
2. Split by newline (`\n`)
3. Trim each line
4. Remove empty lines
5. Each non-empty line is one product code

### Examples

- Cell: `4098-5601\n4098-5207`
  - Codes: `["4098-5601", "4098-5207"]`

- Cell: `2080-9060`
  - Codes: `["2080-9060"]`

- Cell: `INT-GB6\nGBBB`
  - Codes: `["INT-GB6", "GBBB"]`

---

## Selection Type

Set `selection_type` based on the number of product codes **extracted** from Column B (not the number found in DB):
- 1 code extracted → `single`
- 2+ codes extracted → `combo`

---

## Product Matching and Junction Table (CRITICAL)

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

Path: `./backend/seeds/seed_conventional_device_selectables.py`

The script must:

1) Accept Excel path as CLI arg
   Default: `../../Conventional devices.xlsx` (relative to script location — the file in repo root)

2) Read Excel reliably
   Use: `pandas` + `openpyxl` (consistent with existing seed scripts)

3) Parse row by row following the rules above

4) For each valid row, create 1 selectable record and its product links

5) Use a transaction for all inserts

### Idempotency

Before inserting new records:
- Delete all existing selectables with `category = 'conventional_device'`
- This cascades to delete related `selectable_products` records (via ON DELETE CASCADE)
- Then insert fresh from the file

This ensures rerunning the script produces the same result without duplicates.

---

## LLM Device Selection Integration

After seeding conventional devices, the **device selection LLM service** (`backend/app/modules/device_selection/service.py`) must be updated so the LLM knows about conventional devices.

### Catalog Query Change

The current query filters selectables with `WHERE s.category != :exclude_cat` (excluding the opposite addressable protocol). Conventional devices must **never be excluded** — they are always available regardless of protocol.

The query logic should remain the same: `WHERE s.category != :exclude_cat` already works correctly because:
- When protocol is MX → excludes `idnet_detection_device` → conventional_device is NOT excluded
- When protocol is IDNET → excludes `mx_detection_device` → conventional_device is NOT excluded

So **no query change is needed** — conventional devices automatically appear in the catalog.

### LLM System Prompt Update

The SYSTEM_PROMPT in `service.py` must be updated to teach the LLM about conventional devices. Add a new rule:

> **Conventional devices**: The catalog contains conventional (non-addressable) devices with category `"conventional_device"`. These include conventional detectors, switches, manual pull stations, bells, suppression components, and more. A project can use BOTH addressable AND conventional devices simultaneously — they are not mutually exclusive. Even detection can be a mix: addressable smoke detectors alongside conventional smoke detectors in the same project. When a BOQ item clearly describes a conventional/non-addressable device (e.g., "conventional smoke detector", "non-addressable heat detector", "maintenance switch", "abort switch", "conventional bell", "suppression panel"), match it to a conventional_device selectable. Do NOT match conventional BOQ items to addressable selectables or vice versa — respect the explicit conventional/addressable distinction in the BOQ text. If a BOQ item does not specify conventional or addressable, default to the addressable selectable (since addressable is the primary system).

### Rule 10 Update

Current rule 10 says:
> "If a BOQ item is clearly a fire alarm panel, control panel, cable, conduit, or any non-device item, return selectable_id as null."

This must be updated now it should check for the conventional selectables (e.g., `4004-9302` is a 4-Zone Conventional Panel, `4090-9006` is a Suppression Release Kit)as well.
 Update to:
> "If a BOQ item is clearly a cable, conduit, or other non-selectable infrastructure item, return selectable_id as null. For fire alarm panels, suppression panels, and release kits — check if a conventional_device selectable matches. even if they dont find it proper suitable item here then also make its id null."

---

## Run + Verify (Mandatory)

After implementation, you MUST:

1) Create the migration to add `'conventional_device'` to the enum
2) Run `alembic upgrade head`
3) Run the seed script
4) Query DB to confirm:
   - Selectables created with `category = 'conventional_device'`
   - `boq_match_phrases` arrays properly populated from Column C
   - `description` column populated from Column D
   - All `specification_hints` are NULL
   - All `priority` values are NULL
   - `selectable_products` junction records created for products that exist
   - `selection_type` correctly set (`single` vs `combo`)
   - No duplicate selectables
   - Rerun is idempotent

---

## Final Output Required

At the end, print or show:

### Seed Summary
- Total Excel rows read
- Rows skipped (empty)
- Conventional selectables created (total)
- Single selectables count
- Combo selectables count
- Total `selectable_products` links created

### Skipped Selectables Report
A complete list of every selectable that was **skipped** because one or more product codes were not found in the `products` table. For each entry show:
- S. No (row number)
- All Part Numbers from that row
- Which specific codes were missing
- Description

### Missing Products List
A deduplicated list of ALL unique product codes that were not found in the `products` table (across all skipped selectables). This gives a quick overview of which products need to be added to the products table before re-running the seed.

### Sample Records
Show 3-5 sample selectables with:
- category
- selection_type
- boq_match_phrases (first 3)
- description
- linked product codes

---

## Known Missing Products

Based on initial analysis, the following product codes from the file do NOT exist in the `products` table:
- `INT-GB6` — used in rows 12 and 13 (Fire Alarm Bell, Weather Bell)
- `GBBB` — used in row 13 (Weather Bell Back Box)

All other 12 product codes exist. The selectables for rows 12 and 13 should still be created, but with incomplete or no product links.

---

## Deliverables

1) One Alembic migration file that adds `'conventional_device'` to `selectable_category_enum`
2) One standalone seed script file (`./backend/seeds/seed_conventional_device_selectables.py`) that:
   - Reads `./Conventional devices.xlsx`
   - Extracts `boq_match_phrases` from Column C (aliases)
   - Extracts `description` from Column D (Description)
   - Extracts product codes from Column B (Part Numbers)
   - Creates selectables with `category = 'conventional_device'`
   - Links selectables to products via junction table
   - Only creates selectables when ALL product codes exist in the products table
   - Skips the entire selectable if ANY product code is missing
   - Reports all skipped selectables and missing product codes clearly at the end
3) Updates to `backend/app/modules/device_selection/service.py`:
   - Add conventional device rules to the LLM SYSTEM_PROMPT
   - Update rule 10 to not null-out panels/suppression items that now have conventional selectables
4) Proof of running:
   - Seed logs / summary output
   - Sample query output
   - Missing products report

---

## Constraints

- Do NOT change any existing project/spec/boq modules (except the device selection service prompt update).
- Do NOT modify the products table.
- Do NOT modify existing seed scripts for detection or notification devices.
- Keep diffs minimal and consistent with repo patterns.
- Follow the repo's DB connection + migration conventions.
- For Postgres enum changes: use raw SQL in Alembic migrations (not `sa.Enum`).
