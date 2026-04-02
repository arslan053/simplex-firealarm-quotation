# Module: Pricing Calculation & Display

First read and follow `./prompts/workflow_orchestration.md` as mandatory operating rules.

---

## Overview

Build a complete **Pricing** module that calculates the final quotation price for a fire alarm project. The module collects product prices from two sources (device selection + panel selection), converts USD to SAR, applies user-defined margin, adds 15% VAT, and displays a professional quotation-style breakdown.

---

## Data Sources

### Source 1: Device Selection (BOQ Items → Selectables → Products)

Each BOQ item matched to a selectable has linked products via the junction table.

**Data path:**
```
boq_device_selections (id, tenant_id, project_id, boq_item_id, selectable_id, status)
    → selectable_products (selectable_id, product_id)  ← USE THIS for product links
    → products (id, code, price, description)           ← LEFT JOIN (some may be missing)
    + boq_items (id, description, quantity)              ← description + quantity come from HERE
```

**CRITICAL rules — read every single one:**

1. **One pricing row per BOQ item** — key/group on `boq_device_selections.id` (NOT `selectable_id`). Multiple BOQ items can map to the same selectable (e.g., "Addressable control module" qty 355, "Wall mounted door holder" qty 153, and "Floor mounted door holder" qty 30 all map to the "Control Module" selectable). Each BOQ item MUST appear as its own separate row in the pricing table with its own description and quantity. Grouping by `selectable_id` merges them into one row and loses items.

2. **Description = `boq_items.description`** (NOT `selectables.description`). The BOQ description is what the user recognizes from their BOQ document (e.g., "Wall mounted door holder"). The selectable description is a generic category name (e.g., "Control Module") which is meaningless in a quotation.

3. **LEFT JOIN products** (NOT inner JOIN). Some products linked through `selectable_products` may have NULL prices or may not exist. These must still appear in the output marked as missing — never silently dropped.

4. **No JOIN to selectables table needed.** We only need `selectable_products` to get the product links. The selectable's own description is not used.

5. **Fetch products through `selectable_products` junction table** (the live many-to-many link), NOT from the `product_codes` TEXT[] array stored on `boq_device_selections`. The junction table is the source of truth.

6. Only include rows where `boq_device_selections.status = 'finalized'` and `selectable_id IS NOT NULL`.

7. **Ordering**: `ORDER BY bds.created_at` — preserve the natural insertion order. Do NOT sort alphabetically by description or product code.

8. Unit cost = sum of all linked product prices (converted to SAR) for that selectable.

9. Line total = unit cost × `boq_items.quantity`.

10. Show all product codes as inline tags below the description. Missing products get red styling with "(missing)" label.

**BOQ items with no selectable (status = 'no_match' or selectable_id IS NULL):**
- Skip them entirely from the pricing output. Do not show them.

**SQL for device items:**
```sql
SELECT
    bds.id AS bds_id,
    bi.description AS boq_description,
    bi.quantity AS boq_quantity,
    p.code AS product_code,
    p.price AS product_price_usd
FROM boq_device_selections bds
JOIN boq_items bi ON bi.id = bds.boq_item_id
JOIN selectable_products sp ON sp.selectable_id = bds.selectable_id
LEFT JOIN products p ON p.id = sp.product_id
WHERE bds.tenant_id = :tid
  AND bds.project_id = :pid
  AND bds.status = 'finalized'
  AND bds.selectable_id IS NOT NULL
ORDER BY bds.created_at
```

Then group in Python by `bds_id`. Each group = one pricing row.

### Source 2: Panel Selection (Direct Products with Quantities)

Panel products are stored directly with product codes and quantities.

**Data path:**
```
panel_selections (tenant_id, project_id, product_code, quantity)
    → products (code, price, description)   ← LEFT JOIN (some may be missing)
```

**CRITICAL rules:**

1. **Do NOT join or multiply by `panel_groups.quantity`.** The `panel_selections.quantity` is already the final total — the panel selection service pre-multiplies `qty_per_panel × num_panels` before saving. Multiplying by `panel_groups.quantity` again double-counts everything. For example: 6 panels × 1 controller = quantity 6 is already stored. If you multiply by group_quantity 6 again, you get 36 which is wrong.

2. **LEFT JOIN products** (NOT inner JOIN). Some panel selections have `product_code = 'NONE'` or codes that don't exist in the products table. With an inner JOIN these rows silently disappear. They must appear in the output with price SAR 0.00 and marked as missing.

3. When product is missing (LEFT JOIN returns NULL): `description` falls back to the `product_code` string itself, `price = 0`, marked as `missing = true`.

4. **Ordering**: `ORDER BY ps.created_at` — preserve natural insertion order. Do NOT sort alphabetically by product code.

5. Each row in `panel_selections` is one pricing row.

6. Unit cost = product price converted to SAR.

7. Line total = unit cost × `panel_selections.quantity`.

**SQL for panel items:**
```sql
SELECT
    ps.id,
    ps.product_code,
    p.description AS product_description,
    p.price AS product_price_usd,
    ps.quantity AS ps_quantity
FROM panel_selections ps
LEFT JOIN products p ON p.code = ps.product_code
WHERE ps.tenant_id = :tid
  AND ps.project_id = :pid
ORDER BY ps.created_at
```

No join to `panel_groups`. No group multiplier.

---

## Missing Product Handling

Products may be missing from the database (LEFT JOIN returns NULL). This must be handled gracefully, not silently dropped.

**Backend:**
- `ProductDetail` schema has a `missing: bool = False` field
- `PricingItem` schema has a `missing_products: list[str] = []` field (derived from product_details at read time)
- When serializing to JSONB (`product_details` column), include `"missing": true/false` for each product
- When deserializing from JSONB (`get_pricing`), read `d.get("missing", False)` for backwards compatibility

**Frontend:**
- Rows with missing products get a subtle red background (`bg-red-50`)
- Product codes displayed as inline tags; missing ones get red styling + "(missing)" label
- Warning banner above each table section if ANY items in that section have missing products
- CSV export appends "(MISSING)" to missing product codes

---

## Currency Conversion

All product prices in the `products` table are stored in **USD**.

**Conversion to SAR:**
- SAR is pegged to USD at a fixed rate: **1 USD = 3.75 SAR**
- Store this rate as a constant in the backend (not fetched from API)
- All display prices must be in SAR
- Round all SAR amounts to **2 decimal places** using standard rounding (e.g., 2.345 → 2.35, 2.344 → 2.34)

---

## Pricing Calculation

### Per Line Item (Device Selection)

For each BOQ device selection (keyed by `bds.id`):

```
products = fetch via selectable_products junction for the selectable
unit_cost_usd = SUM(product.price for each linked product)  — skip NULL prices
unit_cost_sar = ROUND(unit_cost_usd × 3.75, 2)
quantity = boq_items.quantity
line_total_sar = ROUND(unit_cost_sar × quantity, 2)
```

### Per Line Item (Panel Selection)

For each panel selection product:

```
unit_cost_usd = products.price (looked up by product_code) — 0 if missing
unit_cost_sar = ROUND(unit_cost_usd × 3.75, 2)
quantity = panel_selections.quantity   ← USE AS-IS, already pre-multiplied
line_total_sar = ROUND(unit_cost_sar × quantity, 2)
```

**DO NOT multiply by `panel_groups.quantity`.** The panel selection service already accounts for panel count in the stored quantity.

### Margin

- Default margin: **0%**
- User can enter any percentage value (integer or decimal, e.g., 15, 10.5)
- Margin is applied to each line item's line_total:
  ```
  margin_amount = ROUND(line_total_sar × (margin_percent / 100), 2)
  line_with_margin = line_total_sar + margin_amount
  ```
- The margin column header must dynamically show the percentage: e.g., `"15% Margin"`, `"0% Margin"`, `"10.5% Margin"`
- When margin changes, ALL amounts recalculate immediately

### Subtotal, VAT, Grand Total

```
subtotal = SUM(line_with_margin for all line items)  — both device + panel
vat_amount = ROUND(subtotal × 0.15, 2)              — 15% VAT
grand_total = subtotal + vat_amount
```

- Subtotal, VAT, and Grand Total are displayed at the bottom of the table
- All three recalculate when margin changes

---

## Display Layout

### Header (Letterhead Style)

At the top of the pricing page, display:
- **"Rawabi & Gulf Marvel"** — company name, prominent, styled like a letterhead
- **Project name** — from the project record
- Date of calculation

### Two Sections (Visually Separated)

**Section 1: Device Selection Pricing**

Table columns (6 columns — NO separate Products column):
| # | Description | Qty | Unit Cost (SAR) | Total (SAR) | {X}% Margin |
|---|---|---|---|---|---|
| 1 | BOQ item description _(product codes as tags below)_ | BOQ qty | Sum of product prices in SAR | Unit × Qty | Line total + margin |

- `#` = sequential row number
- `Description` = **`boq_items.description`** on the first line, followed by product codes as inline tags on a second line. Missing products get red tag with "(missing)" label.
- `Qty` = `boq_items.quantity`
- `Unit Cost (SAR)` = sum of all linked product prices converted to SAR
- `Total (SAR)` = unit cost × quantity
- `{X}% Margin` = total + margin applied. Column header changes with margin value.
- Warning banner above this section if any items have missing products

**Section 2: Panel Selection Pricing**

Same table structure (6 columns):
| # | Description | Qty | Unit Cost (SAR) | Total (SAR) | {X}% Margin |
|---|---|---|---|---|---|
| 1 | Product description _(product code tag below)_ | Panel qty | Product price in SAR | Unit × Qty | Line total + margin |

- Visually separated from Section 1 with a clear header like "Panel Configuration"
- `Description` = `products.description` on the first line, product code as inline tag below. Falls back to `product_code` string if product not in DB.
- `Qty` = `panel_selections.quantity` as-is (already pre-multiplied, DO NOT multiply by group)
- Rows with missing products get subtle red background
- Warning banner above this section if any items have missing products

### Footer (Totals)

Below both sections:
```
                              Subtotal:    SAR XX,XXX.XX
                              VAT (15%):   SAR X,XXX.XX
                              Grand Total: SAR XX,XXX.XX
```

### Margin Input

- A clearly visible input field at the top of the pricing page
- Label: "Margin %"
- Default value: 0
- When user changes the value, all margin amounts, subtotal, VAT, and grand total recalculate immediately (frontend-only recalculation — no API call needed for margin changes)
- The column header updates to reflect the new percentage

---

## Backend Architecture

### Module Structure

```
backend/app/modules/pricing/
├── __init__.py
├── router.py      — API endpoints
├── service.py     — Pricing calculation logic
└── schemas.py     — Pydantic request/response models
```

### API Endpoints

**POST** `/api/pricing/{project_id}/calculate`
- Deletes any existing pricing data for this project (idempotent)
- Fetches device selections + panel selections for the project
- Looks up all product prices
- Calculates all line items in SAR
- Stores results in a `pricing_items` table
- Returns the complete pricing breakdown with `calculated_at = datetime.now(UTC).isoformat()`

**GET** `/api/pricing/{project_id}`
- Returns stored pricing data for the project
- Returns 404 or empty if pricing hasn't been calculated yet
- **`calculated_at`** = `max(updated_at)` from the stored `pricing_items` rows, formatted as ISO timestamp. Do NOT use the first item's UUID or any other non-timestamp value.

### Database Table

Create a new table `pricing_items` via Alembic migration:

```sql
CREATE TABLE pricing_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    project_id UUID NOT NULL REFERENCES projects(id),
    section VARCHAR(20) NOT NULL,          -- 'device' or 'panel'
    row_number INTEGER NOT NULL,           -- display order
    description TEXT,                      -- boq_items.description or products.description
    quantity NUMERIC(15,4) NOT NULL,       -- boq_items.quantity or panel_selections.quantity
    unit_cost_sar NUMERIC(15,2) NOT NULL,  -- sum of product prices in SAR
    total_sar NUMERIC(15,2) NOT NULL,      -- unit_cost × quantity
    product_details JSONB NOT NULL,        -- [{code, price_sar, missing}] for each product
    source_id UUID,                        -- bds.id or panel_selection.id
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_pricing_items_project ON pricing_items (tenant_id, project_id);
```

**Idempotency**: The `POST /calculate` endpoint MUST delete all existing `pricing_items` for the project before inserting new ones. Every calculation is a fresh run.

### Calculation Flow (service.py)

```
1. Delete existing pricing_items for (tenant_id, project_id)
2. Fetch device selections:
   - JOIN boq_device_selections → boq_items (for description + quantity)
   - JOIN selectable_products (for product links)
   - LEFT JOIN products (for prices — LEFT to catch missing)
   - WHERE status = 'finalized' AND selectable_id IS NOT NULL
   - ORDER BY bds.created_at
   - Group in Python by bds.id (NOT by selectable_id)
3. For each BOQ item (bds.id group):
   - Sum product prices, convert to SAR
   - Track missing products (NULL price)
   - Create pricing_item with section='device', description=boq_items.description
4. Fetch panel selections:
   - LEFT JOIN panel_selections → products (LEFT to catch missing)
   - NO join to panel_groups (quantity already pre-multiplied)
   - ORDER BY ps.created_at
5. For each panel product:
   - Convert price to SAR (0 if missing)
   - Create pricing_item with section='panel'
6. Bulk insert all pricing_items
7. Return the complete pricing response
```

### Response Schema

```python
class ProductDetail(BaseModel):
    code: str
    price_sar: float
    missing: bool = False

class PricingItem(BaseModel):
    id: str
    section: str              # 'device' or 'panel'
    row_number: int
    description: str | None
    quantity: float
    unit_cost_sar: float
    total_sar: float
    product_details: list[ProductDetail]
    missing_products: list[str] = []   # derived from product_details where missing=True

class PricingResponse(BaseModel):
    project_id: str
    project_name: str
    calculated_at: str        # ISO timestamp — NOT a UUID
    usd_to_sar_rate: float    # 3.75
    items: list[PricingItem]
    device_subtotal: float
    panel_subtotal: float
    subtotal: float           # device + panel totals before margin
```

**`calculated_at` field:**
- On `POST /calculate`: use `datetime.now(timezone.utc).isoformat()`
- On `GET /`: use `max(updated_at).isoformat()` from the stored pricing_items. Fallback to `datetime.now(UTC)` if no timestamp available. **NEVER use `items[0].id`** — that's a UUID, not a timestamp.

**`missing_products` field:**
- Never stored in the database. Derived at read time from `product_details` where `missing=True`.

**JSONB `product_details` serialization:**
- Must include the `missing` field: `[{"code": "X", "price_sar": 0.0, "missing": true}]`
- When deserializing, use `d.get("missing", False)` for backwards compatibility with old rows.

Margin, VAT, and grand total are calculated **on the frontend** from these base amounts — no need to store them since they change dynamically with the margin input.

---

## Frontend Architecture

### Files

```
frontend/src/features/projects/
├── pages/
│   └── PricingPage.tsx              — dedicated pricing page (separate route)
├── components/
│   └── PricingSection.tsx           — main pricing display component (used inside PricingPage)
├── api/
│   └── pricing.ts                   — API calls
└── types/
    └── pricing.ts                   — TypeScript types
```

### Separate Pricing Page

Pricing lives on its **own page**, NOT embedded in `ProjectResultsPage`.

- **Route**: `/projects/:projectId/pricing`
- **Page**: `PricingPage.tsx` — loads project name, renders a back-arrow to results page, and renders `PricingSection`
- **Register** the route in `frontend/src/app/router/index.tsx`
- `PricingPage` uses `max-w-6xl` with responsive padding (`px-4 sm:px-6 lg:px-8`)

### Link from ProjectResultsPage

On `ProjectResultsPage`, add an **"Open Pricing"** card/button at the bottom (after Panel Configuration):
- Shows a card with title "Quotation Pricing" and an "Open Pricing" button
- The button navigates to `/projects/:projectId/pricing`
- The button is **disabled** until panel configuration is completed
- To check panel status: call `panelSelectionApi.getResults()` on mount and check `panel_supported === true && status !== 'empty'`

### Calculate Button (on the Pricing Page)

- The **"Calculate Pricing"** button appears on the pricing page itself (inside `PricingSection`)
- The button is **disabled** until panel selection is complete — `PricingSection` checks `panelSelectionApi.getResults()` on mount to determine readiness
- When panel is not ready, show an amber warning: "Panel analysis and configuration must be completed before pricing can be calculated."

### Pricing Display

- After calculation, show the full pricing table
- The margin input field is at the top
- Changing margin recalculates all margin amounts, subtotal, VAT, and grand total instantly on the frontend (no API call)
- All amounts display with exactly 2 decimal places
- Use SAR formatting with thousands separator: `SAR 12,345.67`
- The page must be **responsive** — usable on desktop, tablet, and mobile
- Use clean spacing: generous padding (`py-3.5`), `tabular-nums` for aligned numbers, `tracking-wider` on table headers
- Use `border border-gray-200` card styling (not heavy shadows) for a clean quotation look

### Missing Product Indicators (Frontend)

- Rows with `missing_products.length > 0` get subtle red background (`bg-red-50/60`)
- Product codes rendered as inline tags (small rounded boxes):
  - Normal products: `bg-gray-100 text-gray-500`
  - Missing products: `bg-red-100 text-red-700` with "(missing)" label
- Warning banner (red, with TriangleAlert icon) above each table section if ANY items in that section have missing products: "Some {device/panel} items have missing products — prices shown as SAR 0.00."

### CSV Download

- A **"Download CSV"** button (outline style) appears next to "Calculate Pricing" when pricing data exists
- Downloads all visible pricing data as a CSV file named `pricing-{projectName}.csv`
- CSV contents: `#, Description, Products, Qty, Unit Cost (SAR), Total (SAR), {margin}% Margin (SAR)`
- Product codes for missing products get "(MISSING)" appended: `"4100-9701 | NONE (MISSING)"`
- Includes section headers (DEVICE SELECTION, PANEL CONFIGURATION)
- Includes Subtotal, VAT (15%), and Grand Total at the bottom of the CSV

### Recalculate

- If the user clicks "Calculate Pricing" again, it:
  1. Shows a confirmation dialog: "This will recalculate all pricing. Continue?"
  2. Calls the POST endpoint (which deletes old + inserts new)
  3. Refreshes the display

---

## Formatting Rules

- All monetary amounts: **2 decimal places**, standard rounding
- Currency display: `SAR` prefix with thousands separator (e.g., `SAR 1,234.56`)
- Margin column header: dynamic, e.g., `"15% Margin"`, `"0% Margin"`
- Quantities: display as integers if whole numbers, up to 2 decimals if fractional

---

## Common Mistakes to Avoid

These are bugs that occurred in the first implementation. Do NOT repeat them:

1. **DO NOT group device items by `selectable_id`.** Multiple BOQ items share the same selectable. Grouping by selectable merges them into one row, losing items and using wrong quantities. Group by `bds.id` instead.

2. **DO NOT use `selectables.description` for device rows.** Use `boq_items.description`. The selectable description is a generic category name, not what belongs in a quotation.

3. **DO NOT multiply panel quantity by `panel_groups.quantity`.** The `panel_selections.quantity` is already the final total (pre-multiplied by the panel selection service). Multiplying again inflates every panel item by Nx.

4. **DO NOT use inner JOIN to products.** Use LEFT JOIN. Inner JOIN silently drops rows where the product doesn't exist in the DB (e.g., `product_code = 'NONE'`). These must appear with price 0 and a missing indicator.

5. **DO NOT use `items[0].id` as `calculated_at` in the GET endpoint.** That's a UUID, not a timestamp. Use `max(updated_at)` from the pricing_items rows.

6. **DO NOT sort alphabetically** by description or product code. Use `ORDER BY created_at` to preserve natural insertion order.

7. **DO NOT forget to include `missing` in the JSONB serialization** of product_details. Without it, the GET endpoint can't reconstruct which products are missing.

---

## Constraints

- Do NOT modify the `products`, `selectables`, `selectable_products`, `boq_items`, `boq_device_selections`, or `panel_selections` tables
- Do NOT modify any existing module logic (device selection, panel selection, BOQ extraction)
- Create a separate `pricing` module under `backend/app/modules/pricing/`
- Register the router in the main app
- Follow existing repo patterns for module structure, auth, tenant isolation
- All queries must filter by `tenant_id` AND `project_id`
- Frontend must follow existing patterns in `frontend/src/features/projects/`

---

## Deliverables

1. **Alembic migration** — create `pricing_items` table with RLS policies
2. **Backend module** — `backend/app/modules/pricing/` with router, service, schemas
3. **Frontend page** — `PricingPage.tsx` as a dedicated page with its own route (`/projects/:projectId/pricing`)
4. **Frontend component** — `PricingSection.tsx` with full pricing table, margin input, totals, CSV download, missing product indicators
5. **Frontend API** — `pricing.ts` API calls
6. **Frontend types** — `pricing.ts` TypeScript interfaces (including `missing` and `missing_products` fields)
7. **Router registration** — add pricing route in `frontend/src/app/router/index.tsx`
8. **Results page link** — add "Open Pricing" card/button on `ProjectResultsPage` (disabled until panel is done)
9. **Backend router registration** — register pricing router in `backend/app/main.py`
10. **Proof of working** — demonstrate calculation with real project data
