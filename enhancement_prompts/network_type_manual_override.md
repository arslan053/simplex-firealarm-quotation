# Enhancement: Network Type Manual Override

## Context

The device selection LLM determines the project's `network_type` (wired / fiber / IP / null) automatically during device selection. However, the LLM can sometimes get it wrong — e.g., picking "wired" when the spec ambiguously mentions both fiber and copper. The user needs the ability to manually override this decision, following the same pattern as the existing protocol (MX/IDNET) override.

The network type affects:
- Which **workstation selectable variant** is picked (wired/fiber/IP workstation)
- Which **networking cards** panel selection adds to the panel (different product codes per type)

---

## What Was Implemented

### 1. Database: `network_type_auto` column on `projects` table

**Migration:** `backend/alembic/versions/030_add_network_type_auto.py`

Added `network_type_auto VARCHAR(10)` — tracks the LLM's original decision separately from the user's manual override (`network_type`). Backfills existing rows from `network_type`.

**Two-column pattern** (same as protocol/protocol_auto):
- `network_type` — the active value (can be changed by user)
- `network_type_auto` — the original AI decision (never changes after device selection)

**Model:** `backend/app/modules/projects/models.py`

```python
network_type: Mapped[str | None] = mapped_column(String(10), nullable=True, default=None)
network_type_auto: Mapped[str | None] = mapped_column(String(10), nullable=True, default=None)
```

### 2. Device Selection Service — Store Both Values

**File:** `backend/app/modules/device_selection/service.py`

In step 5b, when storing the LLM's network_type decision:

```python
UPDATE projects SET network_type = :nt, network_type_auto = :nt WHERE id = :pid AND tenant_id = :tid
```

Both columns are set equal initially. When the user overrides, only `network_type` changes — `network_type_auto` preserves the original.

### 3. Backend API Endpoint

**File:** `backend/app/modules/device_selection/router.py`

#### GET /results — returns both values

The results endpoint now queries `Project.network_type` and `Project.network_type_auto` and includes them in `DeviceSelectionResultsResponse`.

#### PUT /device-selection/network-type — manual override

```python
class NetworkTypeOverrideRequest(BaseModel):
    network_type: str  # "wired", "fiber", or "IP"
```

- Validates value is one of: `"wired"`, `"fiber"`, `"IP"`
- Updates only `Project.network_type` (leaves `network_type_auto` untouched)
- Returns `{"network_type": "...", "message": "..."}`

**Note:** This endpoint only changes the project column — it does NOT re-run device selection. The workstation selectable and networking cards will use the new value when panel selection runs next.

### 4. Frontend UI

**File:** `frontend/src/features/projects/components/DeviceSelectionSection.tsx`

- **Location:** Below the device selection results table
- **Visibility:** Only shown when `network_type` has a value (hidden when null = no networking needed)
- **Toggle:** Cycles through wired → fiber → IP → wired via a "Switch to [next]" button
- **Colors:** Blue for wired, purple for fiber, teal for IP
- **Warning:** When `network_type !== network_type_auto`: amber text "System suggested [auto], manually changed to [current]"

**Files:**
- `frontend/src/features/projects/api/device-selection.api.ts` — added `overrideNetworkType()` method
- `frontend/src/features/projects/types/device-selection.ts` — added `network_type` and `network_type_auto` to `DeviceSelectionResultsResponse`

---

## Files Modified

| File | Change |
|------|--------|
| `backend/alembic/versions/030_add_network_type_auto.py` | **Created** — migration adding `network_type_auto` column with backfill |
| `backend/app/modules/projects/models.py` | **Modified** — added `network_type_auto` field |
| `backend/app/modules/device_selection/service.py` | **Modified** — stores both `network_type` and `network_type_auto` |
| `backend/app/modules/device_selection/schemas.py` | **Modified** — added fields to `DeviceSelectionResultsResponse` |
| `backend/app/modules/device_selection/router.py` | **Modified** — results returns both values, new PUT endpoint |
| `frontend/src/features/projects/components/DeviceSelectionSection.tsx` | **Modified** — network type toggle UI |
| `frontend/src/features/projects/api/device-selection.api.ts` | **Modified** — added `overrideNetworkType()` |
| `frontend/src/features/projects/types/device-selection.ts` | **Modified** — added response fields |

---

## How to Re-apply This Enhancement

1. **Create migration** to add `network_type_auto VARCHAR(10)` nullable column to `projects` table. Backfill from existing `network_type` values.

2. **Add `network_type_auto` field** to the `Project` model as `Mapped[str | None]`.

3. **Update device selection service** (`run()` method, step 5b): change the UPDATE to set BOTH `network_type` and `network_type_auto` when storing the LLM's decision. Both equal initially.

4. **Add PUT endpoint** at `/device-selection/network-type`:
   - Accept `{"network_type": "wired"|"fiber"|"IP"}`
   - Validate the value
   - Update only `Project.network_type` (not `network_type_auto`)
   - Return the new value

5. **Update results endpoint** to query and return both `network_type` and `network_type_auto` from the project.

6. **Update frontend schemas** to include both fields in the results response type.

7. **Add frontend toggle UI** below device selection results:
   - Only visible when `network_type` is not null
   - Cycles through wired → fiber → IP
   - Shows warning when manually changed from auto value

---

## Key Design Decisions

- **Simple column update, no re-selection** — changing network type only updates the project column. The downstream effect happens when panel selection runs (it reads `project.network_type` to pick networking cards). The workstation selectable is NOT re-selected — this is intentional since the user may want to re-run device selection manually.
- **Three-way cycle** — unlike protocol (binary MX/IDNET toggle), network type has three values, so the button cycles through them.
- **Hidden when null** — if the project has no networking (no workstation, no multi-panel), the toggle doesn't appear since there's nothing to override.
- **`network_type_auto` is immutable after device selection** — only `network_type` changes on user override. This lets the UI always show what the system originally suggested.
