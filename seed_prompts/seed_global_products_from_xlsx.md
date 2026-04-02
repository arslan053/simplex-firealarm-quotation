strobe
strsssss# Seed: Global Products Catalog from Excel (Independent Script + Global Table)

You are working inside an existing monorepo that already contains:
- Projects, specs, BOQ, multi-tenancy, RLS patterns, migrations, DB access utilities

IMPORTANT:
- This task is **independent** from the main project modules.
- Do NOT modify any existing project/spec/boq logic.
- Do NOT add tenant isolation to this new table. This table is **GLOBAL** across all companies.
- Keep changes minimal, professional, and consistent with repo migration patterns.

Reference style/patterns for db tables pattrens:
- `./prompts/spec_pdf_md_extraction_prompt.md`
- `./prompts/spec_md_to_db_prompt.md`
- `./prompts/boq_pdf_images_extension_prompt.md`

---

## Goal

1) Create a **GLOBAL** DB table that stores the standard Products catalog (Simplex / Fire Alarm items).
2) Create a **single standalone seed script** that loads an Excel file named **`products.xlsx`** and inserts/updates products into the table.
3) The Excel has columns (exact names may vary slightly; confirm from the file):
   - Product Part Code (or similar)
   - Description
   - Price (USD)
   - Category

Rules:
- Store these columns in DB:
  - `code` (Product Part Code) — store as-is (trim only)
  - `description` — store as-is (trim only)
  - `price` — numeric (parse from USD values like `$1,234.50`)
  - `currency` — store as `"USD"` for all rows
  - `category` — MUST be one of the defined enum categories (NOT NULL)
- If any row is missing required data (code/description/category) → **skip that row**.
- Category in Excel is messy (typos/quotes/casing). You MUST normalize & map to a strict enum so no product has NULL category.
- Script must be safe to rerun (idempotent) using upsert.
- After implementation, you MUST run the script locally and verify rows inserted correctly.
- Finally print the created table schema: table name + column names + types + enum values.

---

## Step 0 — Explore Repo + DB (Mandatory)

Before you write code:
1) Locate how the repo:
   - runs migrations
   - connects to Postgres
   - applies RLS / multi-tenant (observe but do NOT apply to this new table)
2) Inspect the database:
   - list schemas/tables
   - confirm if there is already any "products" table
   - confirm the default schema (public or otherwise)
3) Identify the migration framework used (Prisma/Knex/TypeORM/Drizzle/sql migrations/etc.) and follow the existing pattern.

Do NOT redesign anything.

---

## DB: New Table (GLOBAL, No Multi-Tenancy)

Create ONE table named (choose one, prefer the most consistent naming with repo):
- `products_catalog`
OR more preferable 
- `products`

Use the best repo naming convention. Keep it clear that it is GLOBAL.

### Category Enum (Postgres enum type)

Create a Postgres enum type (name it consistently, e.g. `product_category_enum`) with enum style values also evaluate. should a category be seen as plural or singular:

- `MX Devices`
- `Idnet Devices`
- `IDNAC`
- `Audio Panel`
- `Special Items`
- `conventional`
- `PC-TSW`
- `mimic panel`
- `Panel`
- `Remote Annunciator`
- `Repeator`

Notes:
- Category cannot be NULL.
- Keep enum values exactly as above (case + spacing).

### Columns (short names)

Minimum required:

- `id` UUID PK (default generated)
- `code` TEXT NOT NULL
- `description` TEXT NOT NULL
- `price` NUMERIC NOT NULL  (USD numeric value)
- `currency` TEXT NOT NULL DEFAULT 'USD'
- `category` `product_category_enum` NOT NULL
- `created_at` TIMESTAMP NOT NULL DEFAULT NOW()
- `updated_at` TIMESTAMP NOT NULL DEFAULT NOW()

Constraints / indexes:
- Add `UNIQUE(code)` to support idempotent upsert.
- Keep indexes minimal.

Tenant rules:
- Do NOT add organisation_id/company_id/tenant_id.
- Do NOT apply tenant RLS policies to this table.

---

## Category Normalization + Mapping (Mandatory)

Excel category column values can be messy. You must map all rows to the enum values above.

### Enum categories (final targets)
- MX Devices
- Idnet Devices
- IDNAC
- Audio Panel
- Special Items
- conventional
- PC-TSW
- mimic panel
- Panel
- Remote Annunciator
- Repeator

### Mapping rules (given)
You MUST implement these mappings:

- `Mx Catageroy`, `Mx Category` → `MX Devices`
- `Idnet Catageroy` → `Idnet Devices`
- `Addressable Notification` → `IDNAC`
- `Audio Panel` → `Audio Panel`
- `Back Boxes`, `Clock System`, `Special Items`, `Enclosures`, `Remote LED`, `Telephone FFT`, `"Special Items "`, `Fire Supression` → `Special Items`
- `Conventional`, `"conventional"`, `conventional`, `Conventional Devices` → `conventional`
- `Graphics` → `PC-TSW`
- `mimic panel` → `mimic panel`
- `Panel Items`, `Panel` → `Panel`
- `Remote Annunciator` → `Remote Annunciator`
- `Repeator`, `"Repeator"` → `Repeator`

### Robust normalization (required)
Before mapping:
- Trim whitespace
- Remove surrounding quotes (single/double)
- Collapse repeated spaces
- Case-fold for comparison (e.g., lowercase comparison) BUT final stored enum value must match exact enum spelling.

### Handling misspellings / unknowns
You believe all categories exist but there might be spelling mistakes. Implement:
1) Direct lookup after normalization (dictionary mapping).
2) Fuzzy match fallback (e.g., Python `difflib.get_close_matches` or similar) against:
   - known source keys (mapping keys)
   - final enum targets
3) If still unknown:
   - Do NOT leave category empty.
   - **Assign `Special Items` as safe fallback**
   - Print a warning log entry showing:
     - row number
     - raw category
     - normalized category
     - fallback chosen

This guarantees category is never NULL.

---

## Script: Load `products.xlsx` → Insert/Upsert

Create a SINGLE script file in a clearly separate location (seed/util):
Suggested path (pick the best match to repo style):
- `./scripts/seed_global_products.py`

The script must:
1) Accept the Excel path as CLI arg (default to `products.xlsx` in repo root if arg not provided).
2) Read the Excel using a reliable library (prefer pandas + openpyxl if available).
3) Detect the correct columns even if names vary slightly:
   - Code column: match common variants like `code`, `part code`, `product part code`, `part number`, `model`
   - Description column: `description`, `product description`
   - Category column: `category`
   - Price column: `price`, `unit price`, `usd price`
   - If required columns cannot be found → fail fast with helpful error showing discovered columns.
4) For each row:
   - Extract `code`, `description`, `category_raw`, `price_usd_raw`
   - Normalize + map category to enum (must be non-null)
   - Parse price:
     - Strip `$`, commas, whitespace
     - Convert to numeric (prefer Decimal/NUMERIC-safe parsing)
     - If price missing/NaN/invalid → store NULL in DB for that row
   - Set `currency = "USD"`
   - If code/description/category missing → skip row
5) Insert with UPSERT:
   - On conflict `code`, update:
     - `description`
     - `category`
     - `price`
     - `currency`
     - `updated_at`
6) Print a clear summary:
   - total rows parsed
   - inserted
   - updated
   - skipped (missing required fields)
   - warnings (unknown categories that used fallback)
7) Safety:
   - Use a DB transaction for upserts
   - Do NOT modify any other tables

Idempotency:
- Rerunning script must not duplicate; only update changed rows.

---

## Run + Test (Mandatory)

After implementation, you MUST:
1) Run migrations to create enum + table.
2) Run the seed script against `products.xlsx`.
3) Query DB to confirm:
   - row count matches expected
   - no NULL categories
   - prices are numeric (or NULL when missing)
   - currency always `USD`
   - `UNIQUE(code)` works
4) Rerun the script to ensure idempotency (updates not duplicates).

---

## Final Output Required

At the end, print:
- Table name
- Column names + types
- Constraints (PK + UNIQUE)
- Enum name + enum values
- Example: show first 10 rows in console output (code, category, price, currency, description)

---

## Deliverables

1) DB migration creating:
   - `product_category_enum` (or consistent enum name)
   - GLOBAL products table (no tenancy columns/policies)
2) One standalone seed script file that loads `products.xlsx` and upserts rows.
3) Proof of running it:
   - console output logs
   - schema output
   - sample rows output

---

## Constraints

- Do NOT change any existing project/spec/boq modules.
- This is a separate seed utility only.
- Keep diffs minimal and consistent with repo patterns.
- Follow the repo’s DB connection + migration conventions.
