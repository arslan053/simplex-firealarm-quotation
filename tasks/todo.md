# BOQ → Product Selection Module

## Plan

### Backend
- [x] 1. Migration `011_boq_product_matches.py` — store per-item match results (tenant-scoped, RLS)
- [x] 2. Model `backend/app/modules/boq_product_selection/models.py`
- [x] 3. Prompt file `prompts/boq_product_selection_prompt.md`
- [x] 4. Service `backend/app/modules/boq_product_selection/service.py` — orchestrate sequential LLM calls
- [x] 5. Schemas `backend/app/modules/boq_product_selection/schemas.py`
- [x] 6. Router `backend/app/modules/boq_product_selection/router.py` — run (background job) + status + results
- [x] 7. Register router in `main.py` + import model in `alembic/env.py`

### Frontend
- [x] 8. Types `boq-product-selection.ts`
- [x] 9. API `boq-product-selection.api.ts`
- [x] 10. Component `BoqProductSelectionSection.tsx` — run button + results table with pagination
- [x] 11. Integrate into `ProjectDetailPage.tsx`

### Verification
- [x] 12. Run migration — success
- [x] 13. Verify backend starts without errors — OK
- [x] 14. Verify frontend compiles — only pre-existing errors, new code clean
- [x] 15. Verify DB table — schema, constraints, RLS all correct

---

# Global Products Catalog

## Backend
- [x] 1. Migration `013_products.py` — `product_category_enum` (11 values) + `products` table (no tenant, no RLS)
- [x] 2. Seed script `backend/seeds/seed_products.py` — reads `products.xlsx`, normalizes 23 category variants → 11 enums, upserts 955 rows

## Verification
- [ ] 3. Run migration → confirm table + enum created
- [ ] 4. Run seed script → confirm 955 rows processed
- [ ] 5. `SELECT count(*) FROM products` → expect ~955
- [ ] 6. `SELECT count(*) FROM products WHERE category IS NULL` → expect 0
- [ ] 7. `SELECT DISTINCT currency FROM products` → expect only 'USD'
- [ ] 8. Rerun seed script → confirm idempotent (updates, no duplicates)
- [ ] 9. Print first 10 rows + final total count

---

# Selectables Module — Detection Devices

## Backend
- [x] 1. Migration `014_selectables.py` — `selectable_category_enum` (4 values), `selection_type_enum` (2 values), `selectables` table, `selectable_products` junction table (FKs + unique constraint)
- [x] 2. Seed script `backend/seeds/seed_detection_device_selectables.py` — reads `detection_devices.xlsx`, creates IDNet + MX selectables with descriptions, spec hints, and product links

## Verification
- [x] 3. Run migration → enums + tables created
- [x] 4. Run seed script → 37 rows, 1 skipped, 34 IDNet + 36 MX = 70 selectables
- [x] 5. Descriptions arrays populated correctly
- [x] 6. Specification hints stored with `Refer to project specifications for:` prefix
- [x] 7. Selection types correct (single vs combo based on extracted code count)
- [x] 8. Rerun is idempotent — same 70 selectables, no duplicates
- [ ] 9. Product links pending — products table empty (products.xlsx not yet available)

---

# Selectables Module — Notification Appliances

## Backend
- [x] 1. Seed script `backend/seeds/seed_notification_appliance_selectables.py` — reads `Notification Appliances.xlsx`, detects section headers for category, creates selectables only for matched products

## Verification
- [x] 2. Run seed script → 99 rows, 8 skipped (header + sections + empty), 90 data rows processed
- [x] 3. Section headers detected: NON-ADDRESSABLE → `non_addressable_notification_device`, ADDRESSABLE → `addressable_notification_device`
- [x] 4. All selection_type = `single`, all specification_hints = NULL
- [x] 5. Rerun is idempotent — detection device selectables (70) remain intact
- [x] 6. Unmatched products clearly reported with row, code, description, category
- [ ] 7. Product links + selectables pending — products table empty (products.xlsx not yet available)

---

# Device Selection Module

## Backend
- [x] 1. Migration `015_boq_device_selections.py` — tenant-scoped table with RLS, FK to boq_items + selectables
- [x] 2. Service `backend/app/modules/device_selection/service.py` — loads BOQ items, selectables with product info, spec text, calls GPT-5.2 in batches
- [x] 3. Schemas `backend/app/modules/device_selection/schemas.py` — JobStart/Status, DeviceSelectionItem, paginated results
- [x] 4. Router `backend/app/modules/device_selection/router.py` — run (background job) + status + paginated results
- [x] 5. Register router in `main.py`

## Frontend
- [x] 6. Types `device-selection.ts`
- [x] 7. API `device-selection.api.ts`
- [x] 8. Page `DeviceSelectionPage.tsx` — run button, polling, paginated results table
- [x] 9. Route added to `router/index.tsx`
- [x] 10. Navigation button added to `ProjectDetailPage.tsx`

## Verification
- [ ] 11. Run migration → confirm table + RLS created
- [ ] 12. Navigate to project → click "Device Selection" → arrives at new page
- [ ] 13. Click "Run Device Selection" → background job starts, status polls
- [ ] 14. On success → results table shows matched devices with product codes
- [ ] 15. Verify combo preference in detection devices
- [ ] 16. Verify panels are skipped (selectable_id null)
- [ ] 17. Verify temp product codes display correctly
- [ ] 18. Verify pagination works
