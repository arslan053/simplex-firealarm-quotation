# Enhancement: Deferred Repeater Panel Resolution

## Problem Statement

During device selection, the LLM matches each BOQ item to a selectable product. However, **repeater panels** cannot be fully resolved at device selection time because the correct repeater variant depends on which **main panel** the project uses (4007ES, 4010ES, or 4100ES) — a decision that happens **after** device selection, during the panel selection step.

Currently, the LLM is forced to either:
- Guess a repeater variant (often wrong — gets corrected only after panel decision)
- Return `null` (losing the confident identification that the BOQ item IS a repeater)

Neither outcome is acceptable. We need a structured intermediate state.

---

## Current System Flow (Before This Enhancement)

```
1. BOQ Extraction         → boq_items table populated
2. Spec Analysis          → protocol determined (MX / IDNET)
3. Device Selection (LLM) → boq_device_selections populated (all items resolved or null)
4. Panel Selection (LLM)  → panel type determined (4007 / 4010_1bay / 4010_2bay / 4100ES)
5. Panel Configuration    → panel_selections table populated with products
```

The problem: Step 3 tries to resolve repeater panels, but step 4 hasn't happened yet.

---

## Proposed Flow (After This Enhancement)

```
1. BOQ Extraction         → boq_items table populated
2. Spec Analysis          → protocol determined
3. Device Selection (LLM) → boq_device_selections populated
   └─ Repeater items get status = 'pending_panel' (NOT null, NOT finalized)
4. Panel Selection (LLM)  → panel type determined
5. Repeater Resolution    → auto-triggered after step 4
   └─ Resolves all 'pending_panel' rows → updates to 'finalized'
6. Panel Configuration    → panel_selections populated
7. Frontend refresh       → device selection view shows updated results
```

---

## Database Changes

### Table: `boq_device_selections`

Add a new column `status` to distinguish between resolution states.

```sql
-- Migration: add status column to boq_device_selections
ALTER TABLE boq_device_selections
ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'finalized';
```

**Status values:**

| Status | Meaning |
|---|---|
| `finalized` | LLM returned a direct product match (normal case). Also used after deferred resolution completes. |
| `no_match` | LLM could not find any matching selectable (existing null case). |
| `pending_panel` | Item confidently identified as a repeater panel, but cannot be resolved until main panel type is known. Awaiting panel selection. |

**Backfill existing data:**

```sql
-- Existing rows with selectable_id NOT NULL → 'finalized'
-- Existing rows with selectable_id IS NULL → 'no_match'
UPDATE boq_device_selections SET status = 'finalized' WHERE selectable_id IS NOT NULL;
UPDATE boq_device_selections SET status = 'no_match' WHERE selectable_id IS NULL;
```

### Optional: Add `deferred_type` column

For future extensibility (other items may need deferred resolution), add a nullable marker column:

```sql
ALTER TABLE boq_device_selections
ADD COLUMN deferred_type VARCHAR(30) NULL;
```

For repeater panels, set `deferred_type = 'repeater_panel'`. This allows querying all deferred items by type without relying on string matching in the `reason` column.

---

## LLM Device Selection Changes

### File: `backend/app/modules/device_selection/service.py`

#### SYSTEM_PROMPT Update (Rule 14b modification)

Update the existing rule 14(b) about repeater panels to instruct the LLM to return a special structured marker instead of forcing a product selection:

```
(b) Repeater / Annunciator Panels — When a BOQ item mentions "annunciator",
"repeater", or "LCD panel", DO NOT select a specific repeater panel product.
Instead, return selectable_id as the special value "__PENDING_PANEL__" and
set the reason to explain what was detected (e.g., "Repeater panel identified
— awaiting main panel type decision to select correct variant").
The repeater panel variant (4100ES, 4010, or 4007) depends on which main
panel the project uses, which is determined in a later step.
The selectables catalog contains repeater panels with specification_hints
like "If panel selected is from 4100es series" / "4010es series" /
"4007es series" — these confirm that resolution requires panel type knowledge.
```

#### Output Format Update

The LLM output format should clarify the special marker:

```json
{
  "matches": [
    {
      "boq_item_id": "<uuid>",
      "selectable_id": "__PENDING_PANEL__",
      "reason": "Repeater panel identified — awaiting main panel type decision"
    }
  ]
}
```

#### Service Processing Update

In the `run()` method, when processing LLM matches (step 6), detect the special marker:

```python
# When storing matches:
if selectable_id == "__PENDING_PANEL__":
    # Store as pending_panel — no product codes yet
    status = "pending_panel"
    deferred_type = "repeater_panel"
    selectable_id = None  # No selectable assigned yet
    sel_type = "none"
    p_codes = []
    p_descs = []
elif selectable_id is None:
    status = "no_match"
    deferred_type = None
else:
    status = "finalized"
    deferred_type = None
```

The INSERT statement must include the new `status` and `deferred_type` columns:

```sql
INSERT INTO boq_device_selections
    (tenant_id, project_id, boq_item_id, selectable_id,
     selection_type, product_codes, product_descriptions, reason,
     status, deferred_type)
VALUES (...)
ON CONFLICT (boq_item_id) DO UPDATE SET
    selectable_id = EXCLUDED.selectable_id,
    selection_type = EXCLUDED.selection_type,
    product_codes = EXCLUDED.product_codes,
    product_descriptions = EXCLUDED.product_descriptions,
    reason = EXCLUDED.reason,
    status = EXCLUDED.status,
    deferred_type = EXCLUDED.deferred_type,
    updated_at = now()
```

---

## Repeater Resolution Step (Post-Panel-Selection)

### File: `backend/app/modules/panel_selection/service.py`

After panel selection completes and the panel type is determined (step 7 in `run()`), call a new method to resolve deferred repeater panels.

#### New Method: `_resolve_deferred_repeaters()`

```python
async def _resolve_deferred_repeaters(
    self,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    panel_type: str,  # e.g., "4007", "4010_1bay", "4010_2bay", "4100ES"
) -> int:
    """Resolve all pending_panel repeater items now that panel type is known.

    Returns the number of items resolved.
    """
```

#### Resolution Logic

1. **Find all pending repeater rows:**

   ```sql
   SELECT bds.id, bds.boq_item_id
   FROM boq_device_selections bds
   WHERE bds.tenant_id = :tid
     AND bds.project_id = :pid
     AND bds.status = 'pending_panel'
     AND bds.deferred_type = 'repeater_panel'
   ```

2. **If none found → return early (0 resolved)**

3. **Determine which repeater panel series to use from the decided panel type:**

   | Panel Type | Repeater Series Hint Keyword |
   |---|---|
   | `4007` | `4007es` |
   | `4010_1bay` | `4010es` |
   | `4010_2bay` | `4010es` |
   | `4100ES` | `4100es` |

4. **Query the matching repeater selectable:**

   ```sql
   SELECT s.id, s.selection_type, s.description, s.specification_hints,
          COALESCE(
              array_agg(DISTINCT p.code) FILTER (WHERE p.code IS NOT NULL),
              '{}'
          ) AS product_codes,
          COALESCE(
              array_agg(DISTINCT p.description) FILTER (WHERE p.description IS NOT NULL),
              '{}'
          ) AS product_descriptions
   FROM selectables s
   LEFT JOIN selectable_products sp ON sp.selectable_id = s.id
   LEFT JOIN products p ON p.id = sp.product_id
   WHERE s.description = 'Repeator Panel'
     AND s.category = 'annunciator_subpanel'
     AND LOWER(s.specification_hints) LIKE :hint_pattern
   GROUP BY s.id
   ```

   Where `:hint_pattern` is `'%4007es%'` / `'%4010es%'` / `'%4100es%'` based on the panel type.

5. **If no matching selectable found** — log a warning, leave rows as `pending_panel` (don't lose the identification).

6. **Update each pending row:**

   ```sql
   UPDATE boq_device_selections
   SET selectable_id = :sel_id,
       selection_type = :sel_type,
       product_codes = :p_codes,
       product_descriptions = :p_descs,
       reason = :reason,
       status = 'finalized',
       deferred_type = NULL,
       updated_at = now()
   WHERE id = :bds_id
   ```

   Where `reason` is something like:
   `"Repeater panel resolved after panel decision: 4007-ES series selected → matched to Repeator Panel (4007es specification hint)"`

7. **Log the resolution:**

   ```
   "Resolved {count} deferred repeater panel(s) → {panel_series} series"
   ```

#### Integration Point

In `PanelSelectionService.run()`, call this after the panel type is determined but before returning:

```python
# After panel type is decided (both 4100ES and 4007/4010 paths):
resolved = await self._resolve_deferred_repeaters(
    tenant_id, project_id, panel_type
)
if resolved:
    logger.info("Resolved %d deferred repeater panel(s)", resolved)
```

This must be called in ALL code paths that produce a successful panel decision:
- The `_run_4100es()` path (panel_type = "4100ES")
- The 4007/4010 path (panel_type = "4007" / "4010_1bay" / "4010_2bay")

It should NOT be called when panel selection fails (gate_fail) — repeaters remain pending.

---

## Frontend: Automatic View Refresh After Panel Selection

### Current Behavior

The `DeviceSelectionSection` component fetches results on mount and after its own job completes. It does NOT know about panel selection completing.

### Required Behavior

After panel selection finishes, the device selection results view must refresh to show the resolved repeater panels.

### Approach: Event-Driven Refresh

#### Option A — Simple: PanelConfigurationSection triggers a callback (Recommended)

Add a callback prop to `PanelConfigurationSection` (or `PanelAnalysisSection`, whichever triggers panel selection):

```tsx
// ProjectResultsPage.tsx
const [deviceRefreshKey, setDeviceRefreshKey] = useState(0);

<DeviceSelectionSection
  projectId={projectId}
  projectName={projectName}
  refreshKey={deviceRefreshKey}
/>

<PanelConfigurationSection
  projectId={projectId}
  onPanelDecisionComplete={() => setDeviceRefreshKey(k => k + 1)}
/>
```

In `DeviceSelectionSection`, add `refreshKey` to the `fetchResults` dependency:

```tsx
useEffect(() => {
  fetchResults(1);
}, [fetchResults, refreshKey]);
```

This ensures device selection results re-fetch whenever panel selection completes.

#### Option B — Backend Returns Refresh Signal

The panel selection `/results` endpoint could include a flag `repeaters_resolved: true` in its response. The frontend can use this to trigger a device selection refresh. This is more explicit but requires schema changes on the panel selection response.

### Display: Show Pending Status in Device Selection Table

In the device selection results table, show a visual indicator for pending items:

| BOQ Description | Status | Product Codes | Reason |
|---|---|---|---|
| Repeater Panel | **Pending panel decision** | — | Repeater panel identified — awaiting main panel type |
| Smoke Detector | Matched | 4098-9714, 4098-9770 | Photoelectric smoke sensor combo |

After panel selection resolves the repeater:

| BOQ Description | Status | Product Codes | Reason |
|---|---|---|---|
| Repeater Panel | Matched | 4606-9202, 2975-9461 | Repeater panel resolved: 4007-ES series |
| Smoke Detector | Matched | 4098-9714, 4098-9770 | Photoelectric smoke sensor combo |

The frontend `DeviceSelectionItem` type and the backend results query must include the `status` field so the UI can distinguish between finalized, pending, and no-match states.

---

## Relevant Tables & Current Schemas

### `selectables` (repeater panel rows)

```
id                  | category              | selection_type | boq_match_phrases                      | description     | specification_hints
--------------------+-----------------------+----------------+----------------------------------------+-----------------+--------------------------------------------------------------------
6701aabb-...        | annunciator_subpanel  | combo          | {Annunciator,Repeator,LCD panel}       | Repeator Panel  | Refer to project specifications for: If panel selected is from 4100es series
c0d3c115-...        | annunciator_subpanel  | combo          | {Annunciator,Repeator,LCD panel}       | Repeator Panel  | Refer to project specifications for: If panel selected is from 4010es series
8dc07591-...        | annunciator_subpanel  | combo          | {Annunciator,Repeator,LCD panel}       | Repeator Panel  | Refer to project specifications for: If panel selected is from 4007es series
```

### `boq_device_selections` (current schema)

```sql
CREATE TABLE boq_device_selections (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               UUID NOT NULL REFERENCES tenants(id),
    project_id              UUID NOT NULL REFERENCES projects(id),
    boq_item_id             UUID NOT NULL REFERENCES boq_items(id) ON DELETE CASCADE,
    selectable_id           UUID REFERENCES selectables(id),
    selection_type          VARCHAR(10) NOT NULL DEFAULT 'none',
    product_codes           TEXT[],
    product_descriptions    TEXT[],
    reason                  TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_bds_boq_item UNIQUE (boq_item_id)
);
```

### `boq_device_selections` (after migration)

```sql
-- New columns:
status          VARCHAR(20) NOT NULL DEFAULT 'finalized'   -- 'finalized' | 'no_match' | 'pending_panel'
deferred_type   VARCHAR(30) NULL                           -- 'repeater_panel' | NULL
```

### `panel_selections` (used by panel selection service)

```sql
-- Separate table — no changes needed
CREATE TABLE panel_selections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    project_id      UUID NOT NULL,
    product_code    TEXT NOT NULL,
    product_name    TEXT,
    quantity        INTEGER NOT NULL DEFAULT 0,
    source          TEXT,
    question_no     INTEGER,
    reason          TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## Key Repeater Panel Data (from `PANEL_CONFIGS`)

The panel selection service already has repeater panel product codes hardcoded in `child_card_map` under question 17:

| Panel Type | Repeater Products (Q17) | Matches Selectable |
|---|---|---|
| `4007` | `4606-9202`, `2975-9461` | specification_hints contains `4007es` |
| `4010_1bay` | `4606-9102`, `2975-9206` | specification_hints contains `4010es` |
| `4010_2bay` | `4606-9102`, `2975-9206` | specification_hints contains `4010es` |
| `4100ES` | `4603-9101`, `2975-9206` | specification_hints contains `4100es` |

Note: Q17 in `child_card_map` handles repeater panels as a panel child card (whether the project NEEDS a repeater). The deferred resolution in this enhancement handles the DEVICE SELECTION side (matching the BOQ item to a specific selectable). These are two different concerns:
- **Panel selection Q17**: "Does this project need a repeater?" → adds products to panel bill
- **Device selection deferred**: "Which selectable matches the repeater BOQ item?" → fills boq_device_selections

Both should produce consistent results (same product codes).

---

## Migration File

**File**: `backend/alembic/versions/022_add_status_to_device_selections.py`

```
revision = "022"
down_revision = "021"
```

Operations:
1. Add `status VARCHAR(20) NOT NULL DEFAULT 'finalized'` to `boq_device_selections`
2. Add `deferred_type VARCHAR(30) NULL` to `boq_device_selections`
3. Backfill: set `status = 'no_match'` where `selectable_id IS NULL`
4. Add index: `CREATE INDEX ix_bds_status ON boq_device_selections (status) WHERE status != 'finalized'` (partial index for efficient pending lookups)

---

## Files to Modify/Create

| Action | File | Changes |
|---|---|---|
| CREATE | `backend/alembic/versions/022_add_status_to_device_selections.py` | Migration: add `status` + `deferred_type` columns |
| EDIT | `backend/app/modules/device_selection/service.py` | SYSTEM_PROMPT rule 14b update + detect `__PENDING_PANEL__` marker in match processing + include `status`/`deferred_type` in INSERT |
| EDIT | `backend/app/modules/device_selection/router.py` | Include `status` in results query response |
| EDIT | `backend/app/modules/device_selection/schemas.py` | Add `status` field to `DeviceSelectionItem` |
| EDIT | `backend/app/modules/panel_selection/service.py` | Add `_resolve_deferred_repeaters()` method + call it after panel decision |
| EDIT | `frontend/src/features/projects/components/DeviceSelectionSection.tsx` | Accept `refreshKey` prop + show pending status badge |
| EDIT | `frontend/src/features/projects/pages/ProjectResultsPage.tsx` | Pass `refreshKey` + callback between panel and device sections |
| EDIT | `frontend/src/features/projects/types/device-selection.ts` | Add `status` field to `DeviceSelectionItem` type |

---

## Edge Cases

1. **Panel selection fails (gate_fail)**: Repeater rows stay as `pending_panel`. The UI should show them as "Awaiting panel decision". Re-running panel selection and succeeding will resolve them.

2. **Re-running device selection**: The DELETE + re-insert in device selection clears all rows, including previously resolved repeaters. They will be re-identified as `pending_panel` and await the next panel selection run.

3. **Re-running panel selection**: The `_resolve_deferred_repeaters()` runs again, re-resolving any pending items. Already-finalized repeaters (from a previous panel run) are not affected (their status is already `finalized`).

4. **No repeater BOQ items**: The resolution method returns 0 and exits early. No impact.

5. **Multiple repeater BOQ items**: Each one gets resolved independently to the same selectable variant.

---

## Constraints

- Do NOT change the `selectables` table or seed data
- Do NOT change the `panel_selections` table
- Do NOT modify the existing panel selection product logic (Q17 child card handling remains independent)
- The `status` column defaults to `'finalized'` so existing data and non-repeater items are unaffected
- Repeater resolution is deterministic (knowledge-driven from panel type → specification hint matching), not an LLM call
