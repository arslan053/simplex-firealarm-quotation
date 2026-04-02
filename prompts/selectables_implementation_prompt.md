Claude Code: Implement Selectables Module — Schema, Migration & Detection Devices Seed

Read and follow `./prompts/workflow_orchestration.md` as mandatory operating rules before doing anything.

You can see the following files as well if you need the whole context of the project:

- `./prompts/backend_architect.md`
- `./prompts/boq_module_prompt.md`
- `./seed_prompts/seed_global_products_from_xlsx.md`

You have already implemented multi-tenancy + auth foundation, admin dashboard, projects module, BOQ handling, spec extraction, and the global products catalog.

Now implement the **Selectables module** only, exactly as described below.

Do NOT implement pricing logic, product matching against BOQ, rules engine, or quotation export yet.

====================================
WHAT TO IMPLEMENT
====================================

There are two prompt files that define the full scope. Read them both before writing any code:

1) `./prompts/selectables_module_prompt.md`
   — Defines the **data model, schema, enums, tables, and relationships** for selectables.
   — This is the architecture foundation: the `selectables` table, `selectable_products` junction table (many-to-many with existing `products` table), two new enums (`selectable_category_enum`, `selection_type_enum`), and how descriptions and specification hints work.

2) `./seed_prompts/seed_detection_devices_from_xlsx.md`
   — Defines how to **seed detection device selectables** from `./detection_devices.xlsx`.
   — Covers row parsing, description extraction, specification hints renaming, messy product code extraction, product matching via junction table, missing product reporting, and idempotency.

====================================
IMPLEMENTATION ORDER
====================================

Step 1 — Read both prompt files fully before writing any code.

Step 2 — Create the Alembic migration:
   - Two new enums (`selectable_category_enum`, `selection_type_enum`)
   - `selectables` table
   - `selectable_products` junction table with FK constraints and unique constraint
   - Follow existing migration numbering in `./backend/alembic/versions/`

Step 3 — Run the migration and verify tables + enums exist in DB.

Step 4 — Create the detection devices seed script:
   - Follow all rules in `./seed_prompts/seed_detection_devices_from_xlsx.md`
   - Follow the pattern of `./backend/seeds/seed_global_products.py` for DB connection and script structure
   - Place the script in `./backend/seeds/`

Step 5 — Run the seed script against `./detection_devices.xlsx` and verify:
   - Selectables created with correct categories
   - Descriptions arrays populated
   - Specification hints stored with renamed prefix
   - Junction records created linking to products
   - Missing products reported clearly
   - Rerun is idempotent

====================================
CONSTRAINTS
====================================

- Do NOT modify any existing project/spec/boq modules.
- Do NOT modify the existing products table.
- Selectables tables are GLOBAL — no tenant_id, no RLS.
- Keep diffs minimal and consistent with repo patterns.

Start now.
