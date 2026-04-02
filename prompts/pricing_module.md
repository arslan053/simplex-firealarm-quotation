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
boq_device_selections (tenant_id, project_id, boq_item_id, selectable_id, status)
    → selectables (id, description)
    → selectable_products (selectable_id, product_id)  ← USE THIS for product links
    → products (id, code, price, description)
    + boq_items (id, quantity)  ← quantity multiplier
```

**CRITICAL**: Fetch products through `selectable_products` junction table (the live many-to-many link), NOT from the `product_codes` TEXT[] array stored on `boq_device_selections`. The junction table is the source of truth.

**Rules:**
- Only include rows where `boq_device_selections.status = 'finalized'` and `selectable_id IS NOT NULL`
- Description = `selectables.description` (NOT `boq_items.description`)
- Unit cost = sum of all linked product prices (converted to SAR) for that selectable
- Line total = unit cost × `boq_items.quantity`
- Show all product codes as small monospace text below the description in the same cell (no separate "Products" column, no individual prices in the table row)

**BOQ items with no selectable (status = 'no_match' or selectable_id IS NULL):**
- Skip them entirely from the pricing output. Do not show them.

### Source 2: Panel Selection (Direct Products with Quantities)

Panel products are stored directly with product codes and quantities.

**Data path:**
```
panel_selections (tenant_id, project_id, product_code, quantity, source, panel_group_id)
    → products (code, price, description)
    + panel_groups (id, description, quantity, panel_type, is_main)
```

**Rules:**
- Each row in `panel_selections` is one product with a quantity
- Description = `products.description` (from the products table)
- Unit cost = product price converted to SAR
- Line total = unit cost × `panel_selections.quantity`
- If `panel_group_id` is set, multiply by `panel_groups.quantity` as well (panel group represents N identical panels)
- Show product code as small monospace text below the description in the same cell (no separate column)

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

For each finalized BOQ device selection:

```
products = fetch via selectable_products junction for the selectable
unit_cost_usd = SUM(product.price for each linked product)
unit_cost_sar = ROUND(unit_cost_usd × 3.75, 2)
quantity = boq_items.quantity
line_total_sar = ROUND(unit_cost_sar × quantity, 2)
```

### Per Line Item (Panel Selection)

For each panel selection product:

```
unit_cost_usd = products.price (looked up by product_code)
unit_cost_sar = ROUND(unit_cost_usd × 3.75, 2)
quantity = panel_selections.quantity × panel_groups.quantity (if grouped)
line_total_sar = ROUND(unit_cost_sar × quantity, 2)
```

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
| 1 | Selectable description _(product codes below)_ | BOQ qty | Sum of product prices in SAR | Unit × Qty | Line total + margin |

- `#` = sequential row number
- `Description` = `selectables.description` on the first line, followed by all product codes as small grey monospace text on a second line below (e.g., `4098-9714, 4098-9792`)
- `Qty` = `boq_items.quantity`
- `Unit Cost (SAR)` = sum of all linked product prices converted to SAR
- `Total (SAR)` = unit cost × quantity
- `{X}% Margin` = total + margin applied. Column header changes with margin value.

**Section 2: Panel Selection Pricing**

Same table structure (6 columns):
| # | Description | Qty | Unit Cost (SAR) | Total (SAR) | {X}% Margin |
|---|---|---|---|---|---|
| 1 | Product description _(product code below)_ | Panel qty | Product price in SAR | Unit × Qty | Line total + margin |

- Visually separated from Section 1 with a clear header like "Panel Configuration"
- `Description` = `products.description` on the first line, product code as small grey monospace text below
- `Qty` = `panel_selections.quantity` (× `panel_groups.quantity` if applicable)

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
- Returns the complete pricing breakdown

**GET** `/api/pricing/{project_id}`
- Returns stored pricing data for the project
- Returns 404 or empty if pricing hasn't been calculated yet

### Database Table

Create a new table `pricing_items` via Alembic migration:

```sql
CREATE TABLE pricing_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    project_id UUID NOT NULL REFERENCES projects(id),
    section VARCHAR(20) NOT NULL,          -- 'device' or 'panel'
    row_number INTEGER NOT NULL,           -- display order
    description TEXT,                      -- selectable.description or product.description
    quantity NUMERIC(15,4) NOT NULL,       -- boq_items.quantity or panel qty
    unit_cost_sar NUMERIC(15,2) NOT NULL,  -- sum of product prices in SAR
    total_sar NUMERIC(15,2) NOT NULL,      -- unit_cost × quantity
    product_details JSONB NOT NULL,        -- [{code, price_sar}] for each product
    source_id UUID,                        -- selectable_id or panel_selection reference
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
   - JOIN boq_device_selections → selectables → selectable_products → products
   - JOIN boq_items for quantity
   - WHERE status = 'finalized' AND selectable_id IS NOT NULL
3. For each device selection:
   - Sum product prices, convert to SAR
   - Create pricing_item with section='device'
4. Fetch panel selections:
   - JOIN panel_selections → products
   - JOIN panel_groups for group quantity
5. For each panel product:
   - Convert price to SAR
   - Create pricing_item with section='panel'
6. Bulk insert all pricing_items
7. Return the complete pricing response
```

### Response Schema

```python
class ProductDetail(BaseModel):
    code: str
    price_sar: float

class PricingItem(BaseModel):
    id: str
    section: str              # 'device' or 'panel'
    row_number: int
    description: str
    quantity: float
    unit_cost_sar: float
    total_sar: float
    product_details: list[ProductDetail]

class PricingResponse(BaseModel):
    project_id: str
    project_name: str
    calculated_at: str
    usd_to_sar_rate: float    # 3.75
    items: list[PricingItem]
    device_subtotal: float
    panel_subtotal: float
    subtotal: float           # device + panel totals before margin
```

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

### CSV Download

- A **"Download CSV"** button (outline style) appears next to "Calculate Pricing" when pricing data exists
- Downloads all visible pricing data as a CSV file named `pricing-{projectName}.csv`
- CSV contents: `#, Description, Products, Qty, Unit Cost (SAR), Total (SAR), {margin}% Margin (SAR)`
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
4. **Frontend component** — `PricingSection.tsx` with full pricing table, margin input, totals, CSV download
5. **Frontend API** — `pricing.ts` API calls
6. **Frontend types** — `pricing.ts` TypeScript interfaces
7. **Router registration** — add pricing route in `frontend/src/app/router/index.tsx`
8. **Results page link** — add "Open Pricing" card/button on `ProjectResultsPage` (disabled until panel is done)
9. **Backend router registration** — register pricing router in `backend/app/main.py`
10. **Proof of working** — demonstrate calculation with real project data
