# Selectables Module — Data Model, Schema & Relationships

You are working inside an existing monorepo that already contains:
- Multi-tenancy, auth, projects, BOQ, specs, analysis modules
- A **global `products` table** (no tenant scoping) with `code` (TEXT, UNIQUE) as the product identifier
- Existing prompts under `./prompts/` and seed prompts under `./seed_prompts/`

IMPORTANT:
- First read and follow `./prompts/workflow_orchestration.md` as mandatory operating rules if it exists in the repo.
- Then inspect related prompt files under `./prompts/`, especially `backend_architect.md` and `boq_module_prompt.md`.
- Do NOT modify any existing project/spec/boq/products logic.
- Do NOT add tenant isolation to selectables tables. These tables are **GLOBAL** across all tenants.
- Keep changes minimal, professional, and consistent with repo migration patterns.
- Follow the repo's DB connection + migration conventions.

---

## What Are Selectables

A **selectable** represents a logical product selection that can be matched against a BOQ line item. It is the bridge between raw BOQ descriptions and actual products in the catalog.

Key concepts:

- A selectable is **NOT** a product — it is a **selection entry** that points to one or more products.
- A selectable can represent a **single** product or a **combo** (combination of multiple products).
- Each selectable carries multiple **BOQ match phrases** — different wordings that all refer to the same thing. The LLM uses these to match BOQ line items to the correct selectable.
- Selectables carry **specification hints** — extra keywords or phrases that tell the LLM to additionally check the project specification documents for specific indicators. This helps disambiguate between similar selectables that differ only by technical specs.
- A selectable has a **description** — the final display text shown when this selectable is matched to a BOQ item. This is the canonical, human-readable name of the selectable.
- A selectable may have a **priority** — when set to "high", it indicates this selectable should be preferred by the LLM in most common cases when no specification hints or other differentiators tip the scale.
- A selectable links to one or more products via a **many-to-many** junction table.
- A single product can be referenced by many different selectables.

---

## Core Data Model

### 1) `selectables` table

Each record represents one logical selectable item.

#### Columns

- `id` UUID PK DEFAULT gen_random_uuid()
- `category` `selectable_category_enum` NOT NULL
- `selection_type` `selection_type_enum` NOT NULL
- `boq_match_phrases` TEXT[] NOT NULL — array of all description synonyms for this selectable (used by the LLM for matching BOQ items)
- `description` TEXT NULL — the final display description shown when this selectable is selected for a BOQ item
- `specification_hints` TEXT NULL — LLM-readable hint text directing the model to check project BOQ, sometimes specification for specific indicators (see Specification Hints section)
- `priority` TEXT NULL — when set to "high", indicates this selectable is the preferred/default choice among similar candidates. NULL means no priority preference.
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()
- `updated_at` TIMESTAMPTZ NOT NULL DEFAULT now()


### 2) `selectable_products` junction table (many-to-many)

Links selectables to products from the existing `products` table.

#### Columns

- `id` UUID PK DEFAULT gen_random_uuid()
- `selectable_id` UUID NOT NULL FK → selectables.id ON DELETE CASCADE
- `product_id` UUID NOT NULL FK → products.id ON DELETE CASCADE
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()

#### Constraints

- `UNIQUE(selectable_id, product_id)`

---

## Enums

### 1) selectable_category_enum

Postgres enum type representing the category of a selectable.

Values:
- `mx_detection_device`
- `idnet_detection_device`
- `addressable_notification_device`
- `non_addressable_notification_device`

### 2) selection_type_enum

Postgres enum type representing whether a selectable maps to a single product or a combination.

Values:
- `single`
- `combo`

---

## boq_match_phrases Field

The `boq_match_phrases` column is a TEXT[] array that stores all known names and synonyms for this selectable.

Purpose:
- The LLM uses these phrases to match BOQ line items to the correct selectable.
- If a BOQ description closely matches any one of these synonyms, this selectable becomes a candidate.

Example for a multi-detector selectable:
```
["Addressable Multi Detector", "Multi detector", "Multi Sensor", "Combo detector", "Photo Heat Detector", "Photo Heat Sensor", "Combined Photo heat Detector"]
```

Rules:
- Each phrase is trimmed.
- Order is preserved from the source file.

---

## Description Field

The `description` column stores the final, human-readable display text for this selectable.

### Purpose

When a selectable is matched to a BOQ item, this is the value shown in the results table. It is the canonical name of the selectable.

### Storage

- Stored as a single TEXT value (not an array).
- Derived from the source data's description text (the full clean description before splitting into boq_match_phrases, minus any Specs lines).
- For detection devices: the full description text from the Description column (excluding the Specs line).
- For notification devices: the full description text from the Description column.

---

## Specification Hints Field

The `specification_hints` column stores an optional text string that provides extra matching context for the LLM.

### Purpose

When the LLM evaluates a BOQ item against candidate selectables, and a candidate has specification hints, the LLM should **emphasize more to check the project specification documents** for those specific indicators. Even though the LLM already reviews specs for each BOQ item, this field emphasizes and narrows down exactly what to look for — making the LLM more inclined toward this selectable when those indicators are present.

### Storage Format

- The text is stored as a complete, LLM-readable sentence.
- The prefix `Specs` from the source data is replaced with **`Refer to project specifications for`** to make the purpose self-evident to the LLM.
- The content after the colon remains **exactly as written in the source file** — no modifications, no cleanup, no rewording.

### Examples

| Source text in file | Stored value in DB |
|---|---|
| `Specs: no break glass, no double action` | `Refer to project specifications for: no break glass, no double action` |
| `Specs : 88 degree centigrade or 190 degree faranhite` | `Refer to project specifications for: 88 degree centigrade or 190 degree faranhite` |
| `Specs : relay duct detector, HVAC Shutdown in duct detector section` | `Refer to project specifications for: relay duct detector, HVAC Shutdown in duct detector section` |
| *(no Specs line present)* | `NULL` |

---

## Priority Field

The `priority` column stores an optional text value indicating this selectable's preference level.

### Purpose

When the LLM has multiple candidate selectables that match a BOQ item equally well, and no specification hints differentiate them, the LLM should prefer the selectable with `priority = 'high'` over others with NULL priority.

### Values

- `"high"` — this selectable is the preferred/default choice among similar candidates
- `NULL` — no priority preference (the default for most rows)

### Source

If the Excel source file contains a Priority column or priority markers, read the value. If it contains "high" (case-insensitive), store `"high"`. All other rows store `NULL`.

---

## Relationship With Products Table

The existing `products` table has:
- `id` UUID PK
- `code` TEXT NOT NULL UNIQUE
- *(other columns: description, price, currency, category, timestamps)*

The `selectable_products` junction table creates the many-to-many link:
- `selectable_id` → `selectables.id`
- `product_id` → `products.id`

### How Products Are Linked During Seeding

When seeding selectables from data files:
1. Extract product codes from the source data.
2. Look up each code in the `products` table by the `code` column.
3. If found → create a junction record linking the selectable to that product.
4. If NOT found → **log a clear warning** with the selectable details and the missing product code. Do NOT skip the selectable — create it anyway and only link the products that exist. It is acceptable that some selectables will have no product links. The product code information for that selectable will simply not be available, which is fine.

### Selection Type Determination

Set `selection_type` based on the number of product codes **extracted from the source data** (not the number found in DB):
- 1 code extracted → `single`
- 2+ codes extracted → `combo`

---

## Migration Requirements

Create a new Alembic migration following the repo's existing numbering and style (see `/backend/alembic/versions/`).

The migration must:

1. Create `selectable_category_enum` with the 4 values listed above.
2. Create `selection_type_enum` with the 2 values listed above.
3. Create `selectables` table with the columns listed above.
4. Create `selectable_products` junction table with FK constraints (ON DELETE CASCADE) and unique constraint.

---

## Constraints

- Do NOT add `tenant_id` or RLS policies to these tables — they are GLOBAL.
- Do NOT modify any existing tables or modules.
- The `products` table already exists — do NOT recreate it.
- Keep the migration minimal and consistent with repo patterns.
