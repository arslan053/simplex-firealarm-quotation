# Enhancement: Notification Type Manual Override with LLM Reselection

## Context

During device selection, the LLM determines the `notification_protocol` — whether the project uses **addressable** or **non-addressable** notification devices. This decision affects which notification selectables (from category `addressable_notification_device` or `non_addressable_notification_device`) are assigned to notification BOQ items.

The LLM can sometimes get this wrong — e.g., defaulting to non-addressable when the project actually needs addressable notifications. The user needs the ability to manually override this decision. Unlike the network type override (which is just a column change), changing the notification type requires **re-selecting all notification BOQ items** because the selectables come from a completely different category.

---

## What Was Implemented

### 1. Database: `notification_type` and `notification_type_auto` columns

**Migration:** `backend/alembic/versions/031_add_notification_type_to_projects.py`

Added two columns to `projects`:
- `notification_type VARCHAR(20)` — the active value (can be changed by user)
- `notification_type_auto VARCHAR(20)` — the original AI decision

Values: `"addressable"`, `"non_addressable"`, or `NULL`.

**Model:** `backend/app/modules/projects/models.py`

```python
notification_type: Mapped[str | None] = mapped_column(String(20), nullable=True, default=None)
notification_type_auto: Mapped[str | None] = mapped_column(String(20), nullable=True, default=None)
```

### 2. Device Selection Service — Store the LLM's Decision

**File:** `backend/app/modules/device_selection/service.py`

In the batch loop, captures `notification_protocol` from the LLM response:

```python
if "notification_protocol" in parsed:
    raw_np = parsed["notification_protocol"]
    if raw_np in ("addressable", "non_addressable"):
        notification_type = raw_np
```

After all batches (step 5c), stores both columns:

```python
UPDATE projects SET notification_type = :nt, notification_type_auto = :nt
WHERE id = :pid AND tenant_id = :tid
```

### 3. Notification Reselection Service Method

**File:** `backend/app/modules/device_selection/service.py`

New method: `reselect_notifications(tenant_id, project_id, target_type)`

This is the core of the feature. When the user changes notification type:

1. **Find notification BOQ items** — queries `boq_device_selections` joined with `selectables` to find all items currently matched to either `addressable_notification_device` or `non_addressable_notification_device` selectables.

2. **Load target-category selectables** — loads ONLY selectables from the target category (e.g., if switching to addressable, loads only `addressable_notification_device` selectables) with their product codes and descriptions.

3. **Load spec text** — the project specification is included in the LLM call because the notification reselection prompt uses specification hints for disambiguation.

4. **Call LLM** — sends the notification BOQ items + target-category selectables + spec text to GPT-5.2 with the `_NOTIFICATION_RESELECT_PROMPT`.

5. **Update in place** — for each match returned by the LLM, updates the existing `boq_device_selections` row with the new selectable_id, product codes, descriptions, reason, and status. Does NOT delete/recreate — updates the same rows so position and ordering are preserved.

### 4. The Notification Reselection Prompt

**Constant:** `_NOTIFICATION_RESELECT_PROMPT` in `backend/app/modules/device_selection/service.py`

This is a **separate prompt** from the main `SYSTEM_PROMPT`. It is NOT a modification of the existing device selection prompt. Key characteristics:

**Critical constraint at the top:**
```
The user has explicitly set the notification type to {TARGET_TYPE}.
ALL selectables in the catalog are {TARGET_TYPE} notification devices.
Ignore any indication of addressable or non-addressable in the BOQ text
or specification — the user's explicit choice overrides everything.
```

**Matching rules included (carried from main prompt):**
1. **BOQ match phrases** — semantic matching against `boq_match_phrases`
2. **Specification hints (highest priority)** — spec indicators disambiguate similar selectables
3. **Color defaults** — wall → red, ceiling → white (when BOQ doesn't specify)
4. **Mount defaults** — default to wall when BOQ doesn't specify
5. **No combos** — notification devices are always single selectables
6. **Priority preference** — prefer "High" priority selectables (~95% correct), but explicit BOQ/spec attributes override
7. **Semantic matching** — match by meaning, not keyword overlap
8. **No match** — return null if no selectable fits

**Rules NOT included (intentionally excluded):**
- Rule 7 (notification protocol consistency) — not needed since we're forcing the target type
- Rule 12 (conventional panel lock-in) — not relevant for notification reselection
- All detection device rules — only notification items are being reselected
- Network type, workstation, printer rules — not relevant

**Output format:**
```json
{"matches": [{"boq_item_id": "<uuid>", "selectable_id": "<uuid or null>", "reason": "<short explanation>"}]}
```

Simpler than the main prompt output — no `notification_protocol` or `network_type` fields needed.

**The `{TARGET_TYPE}` placeholder** is replaced at runtime with the actual value (`"addressable"` or `"non_addressable"`).

### 5. Backend API Endpoint

**File:** `backend/app/modules/device_selection/router.py`

#### PUT /device-selection/notification-type

```python
class NotificationTypeOverrideRequest(BaseModel):
    notification_type: str  # "addressable" or "non_addressable"
```

Flow:
1. Validates value is `"addressable"` or `"non_addressable"`
2. Updates `Project.notification_type` (leaves `notification_type_auto` untouched)
3. Calls `service.reselect_notifications(tenant_id, project_id, target_type)`
4. Commits the transaction (both project update and device selection updates)
5. Returns `{"notification_type": "...", "updated_count": N, "message": "..."}`

**Important:** This is a synchronous request — the LLM call happens within the HTTP request. This is acceptable because notification reselection is fast (only notification items, not the full BOQ).

### 6. Frontend UI

**File:** `frontend/src/features/projects/components/DeviceSelectionSection.tsx`

- **Location:** Below the network type toggle, above the empty state
- **Visibility:** Only shown when `notification_type` has a value
- **Toggle:** Binary switch between Addressable and Non-Addressable
- **Colors:** Indigo for addressable, orange for non-addressable
- **Confirmation dialog:** Before switching, shows: "Changing notification type to [X] will re-run device selection for all notification items. Currently selected notification devices will be replaced with [X] variants. Are you sure you want to change the notification type?"
- **Loading spinner:** "Re-selecting notification devices..." shown during LLM call
- **Warning:** When manually changed: "System suggested [auto], manually changed to [current]"
- **Auto-refresh:** Results table refreshes after reselection completes

**Files:**
- `frontend/src/features/projects/api/device-selection.api.ts` — added `overrideNotificationType()` method
- `frontend/src/features/projects/types/device-selection.ts` — added `notification_type` and `notification_type_auto` to response

---

## Files Modified

| File | Change |
|------|--------|
| `backend/alembic/versions/031_add_notification_type_to_projects.py` | **Created** — migration adding both columns |
| `backend/app/modules/projects/models.py` | **Modified** — added `notification_type` and `notification_type_auto` fields |
| `backend/app/modules/device_selection/service.py` | **Modified** — stores LLM decision, new `reselect_notifications()` method, new `_NOTIFICATION_RESELECT_PROMPT` |
| `backend/app/modules/device_selection/schemas.py` | **Modified** — added fields to `DeviceSelectionResultsResponse` |
| `backend/app/modules/device_selection/router.py` | **Modified** — results returns both values, new PUT endpoint with reselection |
| `frontend/src/features/projects/components/DeviceSelectionSection.tsx` | **Modified** — notification type toggle with confirmation, spinner, warning |
| `frontend/src/features/projects/api/device-selection.api.ts` | **Modified** — added `overrideNotificationType()` |
| `frontend/src/features/projects/types/device-selection.ts` | **Modified** — added response fields |

---

## How to Re-apply This Enhancement

### Database

1. **Create migration** to add `notification_type VARCHAR(20)` and `notification_type_auto VARCHAR(20)` nullable columns to `projects`.

2. **Add both fields** to the `Project` model.

### Backend — Storing the LLM Decision

3. **In device selection service** (`run()` method): after the batch loop, extract `notification_protocol` from the LLM response. If it's `"addressable"` or `"non_addressable"`, store it as both `notification_type` and `notification_type_auto` on the project. If null/missing, set both to NULL.

### Backend — Reselection Logic

4. **Create `reselect_notifications()` method** on `DeviceSelectionService`:
   - Query `boq_device_selections` joined with `selectables` to find items matched to `addressable_notification_device` or `non_addressable_notification_device`
   - Load selectables ONLY from the target category
   - Load spec text for the project
   - Call LLM with the notification reselection prompt
   - Update each `boq_device_selections` row in place (selectable_id, product_codes, product_descriptions, reason, status)

5. **Write `_NOTIFICATION_RESELECT_PROMPT`** — a separate prompt (NOT modifying the main one) that:
   - States the user explicitly chose the target type — ignore BOQ/spec addressability indicators
   - Includes all notification matching rules: BOQ match phrases, specification hints (highest priority), color defaults (wall→red, ceiling→white), mount defaults (default wall), no combos, priority preference, semantic matching
   - Excludes all non-notification rules
   - Output: simple `{"matches": [...]}` format

### Backend — API Endpoint

6. **Add PUT `/device-selection/notification-type` endpoint**:
   - Validate value is `"addressable"` or `"non_addressable"`
   - Update `Project.notification_type` only
   - Call `reselect_notifications()`
   - Commit and return result with updated count

7. **Update results endpoint** to return `notification_type` and `notification_type_auto` from the project.

### Frontend

8. **Update types** to include both fields in the results response.

9. **Add API method** `overrideNotificationType(projectId, notificationType)`.

10. **Add toggle UI** below device selection results:
    - Only visible when `notification_type` is not null
    - Binary toggle (addressable ↔ non-addressable)
    - Confirmation dialog before switching (warns about reselection)
    - Loading spinner during LLM call
    - Warning when manually changed
    - Auto-refresh results after completion

---

## Key Design Decisions

- **Separate prompt, not modifying the main one** — the reselection prompt is purpose-built for notification re-matching. The main `SYSTEM_PROMPT` remains untouched, avoiding risk of breaking full device selection.
- **Only notification items are sent** — detection devices, conventional devices, annunciators, etc. are not touched. Only BOQ items currently matched to notification selectables are re-processed.
- **Only target-category selectables provided** — the LLM catalog contains ONLY addressable or non-addressable notification selectables (not both). This makes it impossible for the LLM to pick the wrong category.
- **In-place update** — device selection rows are updated, not deleted and recreated. This preserves row order and avoids disrupting other parts of the system that reference `boq_device_selections`.
- **Synchronous request** — unlike full device selection (which uses background jobs + polling), notification reselection is fast enough to run within the HTTP request because it only processes a subset of BOQ items.
- **Spec text included** — specification hints are critical for disambiguation (e.g., choosing between two similar horn strobes where one has specific wattage mentioned in the spec).
- **Panel selection reads from `boq_device_selections`** — panel selection's `_get_notification_type()` method derives the notification type from the selectable categories in `boq_device_selections`. After reselection, all notification items point to the new category, so panel selection automatically picks up the change.
- **Confirmation dialog** — unlike network type (which is just a column change), notification type override triggers an LLM call that replaces device selections. The user must confirm they understand this.
