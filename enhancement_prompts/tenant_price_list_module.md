# Module: Tenant Price List Management

First read and follow `./prompts/workflow_orchestration.md` — treat it as **mandatory operating rules** for this session. Follow existing repo architecture patterns. Do NOT modify unrelated modules. Keep changes minimal and consistent with repo conventions.

---

## Overview

Add per-tenant product pricing. Currently the `products` table has a single global `price` column (USD) shared across all tenants. Each company (tenant) negotiates different prices with Simplex, so every tenant needs its own price list.

### Key Decisions

- **New table** `tenant_product_prices` stores per-tenant prices. The global `products.price` column is **kept** as a default template for new tenants.
- **Pricing service** updated to read from `tenant_product_prices` instead of `products.price`.
- **Sidebar item** "Price List" visible to **admin** role only on tenant portal (not employees, not super_admin).
- **Excel workflow**: System generates a locked template (product id, code, description are read-only), user fills price column, uploads back. System validates id+code+description match before accepting.
- **Inline editing**: Professional table with search, category filter, batch save (user edits multiple prices → clicks "Save Changes" to persist all at once).
- **Seed data**: On migration, populate `tenant_product_prices` for all existing tenants by copying `products.price`.
- **New tenant creation**: When a new tenant is created, copy all product prices from `products` table as defaults.
- **Currency**: `tenant_product_prices` has a `currency` column (default `'USD'`).

---

## Database

### Migration 036: Create `tenant_product_prices`

```sql
CREATE TABLE tenant_product_prices (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    price NUMERIC NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'USD',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    UNIQUE (tenant_id, product_id)
);

CREATE INDEX ix_tpp_tenant ON tenant_product_prices(tenant_id);
```

Follow raw SQL migration pattern. Revision `"036"`, down_revision `"035"`.

### Seed Existing Tenants

After creating the table, populate it for every existing tenant:

```sql
INSERT INTO tenant_product_prices (tenant_id, product_id, price, currency)
SELECT t.id, p.id, COALESCE(p.price, 0), p.currency
FROM tenants t
CROSS JOIN products p
ON CONFLICT (tenant_id, product_id) DO NOTHING;
```

This goes in the migration's `upgrade()` so existing deployments get prices automatically.

### RLS Policy

Add Row-Level Security matching other tenant tables:

```sql
ALTER TABLE tenant_product_prices ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy ON tenant_product_prices
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

CREATE POLICY app_bypass_policy ON tenant_product_prices
    USING (current_setting('app.current_tenant_id', true) IS NULL OR current_setting('app.current_tenant_id', true) = '');
```

---

## Backend Module: `tenant_pricing`

### Structure

```
backend/app/modules/tenant_pricing/
├── __init__.py
├── schemas.py
├── service.py
└── router.py
```

### Schemas (`schemas.py`)

```python
class TenantProductPrice(BaseModel):
    product_id: str
    code: str
    description: str
    category: str
    price: float
    currency: str

class PriceListResponse(BaseModel):
    items: list[TenantProductPrice]
    total: int
    prices_set: int  # count of items where price > 0

class PriceUpdateItem(BaseModel):
    product_id: str
    price: float

class PriceUpdateRequest(BaseModel):
    items: list[PriceUpdateItem]

class PriceUpdateResponse(BaseModel):
    updated: int

class TemplateValidationError(BaseModel):
    row: int
    expected_code: str
    got_code: str
    message: str

class UploadResponse(BaseModel):
    updated: int
    errors: list[TemplateValidationError]
```

### Service (`service.py`)

**`get_price_list(tenant_id, search?, category?)`**
- LEFT JOIN `products` with `tenant_product_prices` on product_id + tenant_id
- Return all 991 products with tenant price (0 if not set)
- Support optional search filter (ILIKE on code + description)
- Support optional category filter
- Order by category, then code

**`update_prices(tenant_id, items: list[PriceUpdateItem])`**
- Batch upsert: `INSERT ... ON CONFLICT (tenant_id, product_id) DO UPDATE SET price = EXCLUDED.price, updated_at = now()`
- Return count of updated rows
- Validate all product_ids exist

**`generate_template(tenant_id) -> bytes`**
- Generate Excel with openpyxl
- Columns: A=Product ID (locked), B=Code (locked), C=Description (locked), D=Price (editable, pre-filled with current tenant price)
- Sheet protection: lock columns A-C, leave D unlocked
- Header row styled (bold, gray background)
- Return Excel bytes

**`process_upload(tenant_id, file_bytes) -> UploadResponse`**
- Parse Excel with openpyxl
- For each row, validate: row's product_id + code + description must match the DB product exactly
- If any mismatch: add to errors list with row number and details, skip that row
- For valid rows: batch upsert prices
- Return count updated + list of errors

### Router (`router.py`)

Prefix: `/api/price-list`

Auth: `require_tenant_domain` + `require_tenant_match` + `require_role("admin")`

Endpoints:
- `GET /api/price-list` — list all products with tenant prices. Query params: `search`, `category`
- `PUT /api/price-list` — batch update prices (inline edits)
- `GET /api/price-list/template` — download Excel template
- `POST /api/price-list/upload` — upload filled template
- `GET /api/price-list/categories` — return list of distinct product categories

### Register in `main.py`

```python
from app.modules.tenant_pricing.router import router as tenant_pricing_router
app.include_router(tenant_pricing_router)
```

---

## Pricing Service Update

### Modify `backend/app/modules/pricing/service.py`

**`_build_device_items()`** — Change the product price source:

```sql
-- Before:
LEFT JOIN products p ON p.id = sp.product_id
-- p.price AS product_price_usd

-- After:
LEFT JOIN products p ON p.id = sp.product_id
LEFT JOIN tenant_product_prices tpp ON tpp.product_id = p.id AND tpp.tenant_id = :tid
-- COALESCE(tpp.price, p.price, 0) AS product_price_usd
```

**`_build_panel_items()`** — Same change:

```sql
-- Before:
LEFT JOIN products p ON p.code = ps.product_code
-- p.price AS product_price_usd

-- After:
LEFT JOIN products p ON p.code = ps.product_code
LEFT JOIN tenant_product_prices tpp ON tpp.product_id = p.id AND tpp.tenant_id = :tid
-- COALESCE(tpp.price, p.price, 0) AS product_price_usd
```

The `COALESCE` ensures fallback to global price if tenant price doesn't exist, then 0 if neither exists.

---

## Tenant Creation: Auto-populate Prices

### Modify `backend/app/modules/tenants/service.py` (or wherever tenant creation happens)

After creating a new tenant, insert default prices:

```sql
INSERT INTO tenant_product_prices (tenant_id, product_id, price, currency)
SELECT :new_tenant_id, p.id, COALESCE(p.price, 0), p.currency
FROM products p;
```

This ensures new companies start with the default Simplex price list instead of empty/0 prices.

---

## Frontend

### Types: `frontend/src/features/tenant-pricing/types/index.ts`

```typescript
export interface TenantProductPrice {
  product_id: string;
  code: string;
  description: string;
  category: string;
  price: number;
  currency: string;
}

export interface PriceListResponse {
  items: TenantProductPrice[];
  total: number;
  prices_set: number;
}

export interface PriceUpdateItem {
  product_id: string;
  price: number;
}

export interface TemplateValidationError {
  row: number;
  expected_code: string;
  got_code: string;
  message: string;
}

export interface UploadResponse {
  updated: number;
  errors: TemplateValidationError[];
}
```

### API: `frontend/src/features/tenant-pricing/api/tenantPricing.api.ts`

```typescript
export const tenantPricingApi = {
  getList: (params?: { search?: string; category?: string }) =>
    apiClient.get<PriceListResponse>('/price-list', { params }),

  updatePrices: (items: PriceUpdateItem[]) =>
    apiClient.put<{ updated: number }>('/price-list', { items }),

  downloadTemplate: () =>
    apiClient.get<Blob>('/price-list/template', { responseType: 'blob' }),

  uploadTemplate: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return apiClient.post<UploadResponse>('/price-list/upload', form);
  },

  getCategories: () =>
    apiClient.get<{ categories: string[] }>('/price-list/categories'),
};
```

### Page: `frontend/src/features/tenant-pricing/pages/PriceListPage.tsx`

**Layout:**

```
┌─────────────────────────────────────────────────────────┐
│  Price List                              [Download] [Upload] │
│  945/991 prices set                                         │
├─────────────────────────────────────────────────────────┤
│  [🔍 Search by code or description...] [Category ▾]        │
├──────┬────────────────────────┬──────────┬──────────────┤
│ Code │ Description            │ Category │ Price (USD)  │
├──────┼────────────────────────┼──────────┼──────────────┤
│ 49AO │ Outdoor Horn Strobe    │ MX Dev.  │  [  37.73 ] │ ← editable
│ 49AO │ Outdoor Horn w/ BA     │ MX Dev.  │  [  42.34 ] │
│ 49AO │ Outdoor Wall Horn      │ MX Dev.  │  [      0 ] │ ← red highlight
│ ...  │ ...                    │ ...      │  [ ... ]    │
├──────┴────────────────────────┴──────────┴──────────────┤
│                              [Save Changes (3 modified)] │
└─────────────────────────────────────────────────────────┘
```

**Behavior:**

1. **Search**: Debounced input (300ms), searches code + description via API query param
2. **Category filter**: Dropdown populated from `/categories` endpoint
3. **Inline editing**: Click price cell → type new value. Modified rows get a subtle left-border highlight (blue). Track modified rows in local state.
4. **Save**: "Save Changes" button appears when there are modifications. Shows count of modified items. Sends batch PUT request. On success: toast/flash message, clear modified state. On error: show message.
5. **Empty prices**: Rows with price = 0 get a subtle red/amber background to indicate they need attention.
6. **Progress indicator**: "945/991 prices set" badge in header area.
7. **Pagination**: Virtual scroll or paginated table (991 rows). Prefer showing all rows with virtual scroll for smooth UX. If too complex, paginate 50 per page.
8. **Download template**: Triggers file download of Excel template.
9. **Upload**: File input → on select, upload immediately → show result dialog with success count + error list if any.

**Save strategy**: Let user make multiple edits → track locally → "Save Changes" button to persist all at once. This is more professional — prevents accidental saves, lets user review before committing, reduces API calls.

### Sidebar: Add "Price List" nav item

**Modify `AppLayout.tsx` → `getNavItems()`:**

```typescript
// After Team Members, admin-only on tenant portal
if (!isAdminDomain && role === 'admin') {
  items.push({ to: '/users', label: 'Team Members', icon: Users });
  items.push({ to: '/price-list', label: 'Price List', icon: DollarSign });
}
```

Import `DollarSign` from lucide-react.

### Router: Add route

**Modify `frontend/src/app/router/index.tsx`:**

```typescript
{ path: 'price-list', element: <PriceListPage /> },
```

---

## Files Summary

### New Files

| File | Purpose |
|------|---------|
| `backend/alembic/versions/036_create_tenant_product_prices.py` | Migration + seed data |
| `backend/app/modules/tenant_pricing/__init__.py` | Module init |
| `backend/app/modules/tenant_pricing/schemas.py` | Pydantic schemas |
| `backend/app/modules/tenant_pricing/service.py` | Business logic |
| `backend/app/modules/tenant_pricing/router.py` | API endpoints |
| `frontend/src/features/tenant-pricing/types/index.ts` | TypeScript types |
| `frontend/src/features/tenant-pricing/api/tenantPricing.api.ts` | API client |
| `frontend/src/features/tenant-pricing/pages/PriceListPage.tsx` | Price list page |

### Modified Files

| File | Change |
|------|--------|
| `backend/app/main.py` | Register tenant_pricing router |
| `backend/app/modules/pricing/service.py` | Use tenant prices in pricing calculations |
| `frontend/src/app/router/index.tsx` | Add /price-list route |
| `frontend/src/app/router/layouts/AppLayout.tsx` | Add Price List nav item (admin only) |

### Files NOT to Modify

- `products` table — keep `price` column as-is (template for new tenants)
- `selectable_products` — no changes
- `selectables` — no changes
- Any migration before 036

---

## Authorization

### Backend
- All `/api/price-list/*` endpoints: `require_role("admin")` only
- Employees cannot view or edit prices
- Super admins don't access tenant price lists (they're on admin portal)

### Frontend
- "Price List" nav item: only shown when `!isAdminDomain && role === 'admin'`
- Employees see no sidebar link and get 403 if they try the URL directly
- Download/Upload/Save buttons all behind admin role check

---

## Excel Template Format

### Download Template

Generated by backend with openpyxl:

| Column A (locked) | Column B (locked) | Column C (locked) | Column D (editable) |
|---|---|---|---|
| **Product ID** | **Code** | **Description** | **Price (USD)** |
| uuid-1 | 49AO-WRF | Outdoor Horn Strobe... | 37.73 |
| uuid-2 | 49AO-WRF-BA | Outdoor Horn w/ BA... | 42.34 |
| ... | ... | ... | ... |

- Columns A-C: locked cells (gray background, font color dark)
- Column D: unlocked, white background, number format
- Sheet protection enabled (password not required — just prevents accidental edits)
- Column widths: A=10 (hidden or narrow), B=15, C=40, D=15

### Upload Validation

For each row in uploaded Excel:
1. Read product_id (col A), code (col B), description (col C), price (col D)
2. Query DB: does a product with this id, code, AND description exist?
3. If **yes**: upsert the price
4. If **no**: add to errors list: `"Row 5: Product ID/code/description mismatch — expected 'Outdoor Horn' got 'Modified Text'"`
5. Skip rows where price is empty/blank
6. Return: `{ updated: 950, errors: [{ row: 5, ... }, { row: 12, ... }] }`

---

## Verification Checklist

1. Migration creates table + populates prices for existing tenants (acme, beta)
2. `GET /api/price-list` returns 991 products with prices for logged-in tenant
3. `PUT /api/price-list` updates multiple prices in one call
4. `GET /api/price-list?search=49AO` returns filtered results
5. `GET /api/price-list?category=MX Devices` returns filtered results
6. `GET /api/price-list/template` downloads Excel with locked columns A-C
7. Upload Excel with correct data → prices updated, 0 errors
8. Upload Excel with modified code in row 5 → error reported for row 5, others updated
9. Pricing calculation for a project uses tenant prices (not global `products.price`)
10. New tenant creation auto-populates 991 price rows from global defaults
11. Sidebar shows "Price List" for admin, hidden for employee
12. Employee gets 403 on `/api/price-list` endpoints
13. Modified prices have visual indicator, "Save Changes" button with count
14. Zero-price rows have amber highlight
15. Search + category filter work together

---

## Implementation Order

1. Migration 036 — create table, seed data, RLS
2. Backend module — schemas, service, router
3. Register router in main.py
4. Update pricing service to use tenant prices
5. Update tenant creation to auto-populate prices
6. Frontend types + API
7. Frontend PriceListPage
8. Sidebar + route registration
9. Test end-to-end
