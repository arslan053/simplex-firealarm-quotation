# Enhancement: Use Q21 Loop Count for 4100ES Loop Cards in Multi-Panel Mode

## Problem Statement

In **multi-panel-group mode**, when `_run_multi_group()` calls `_build_4100es_products()` for the main 4100ES panel group, the loop card quantity (Step 4) is calculated by dividing total devices by per-loop capacity:

```python
qty_loop = math.ceil(total_devices / 150)   # MX protocol
qty_loop = math.ceil(total_devices / 200)   # IDNET protocol
```

But in multi-panel-group mode, each group already has an explicit `loop_count` from BOQ panel items (e.g. "12-loop panel"). The loop card count should be **exactly the stated loop count** — not derived from device count. A 12-loop main panel needs 12 loop cards, period.

This is analogous to the existing `nac_override_loops` parameter that already overrides NAC card calculation in multi-panel mode.

**IMPORTANT:** This change applies **only** to the multi-panel-group path (`_run_multi_group()`). The single-panel legacy path (`_run_4100es()`) continues to use the device-division formula unchanged.

---

## Affected Path

**Only** the multi-panel-group 4100ES main panel path in `_run_multi_group()`.

| Path | Loop card behavior |
|---|---|
| **Single-panel 4100ES** (`_run_4100es()`) | **UNCHANGED** — `ceil(devices / 150 or 200)` legacy formula |
| **Multi-panel-group 4100ES main** (`_run_multi_group()`) | **OVERRIDE** — uses `main_group["loop_count"]` directly |
| **4007 / 4010 (any path)** | **UNCHANGED** — no loop card step |

---

## Implementation

**File:** `backend/app/modules/panel_selection/service.py`

### 1. Add `loop_card_override` parameter to `_build_4100es_products()`

Add a new optional parameter alongside the existing `nac_override_loops`:

```python
nac_override_loops: int | None = None,
loop_card_override: int | None = None,    # NEW
```

### 2. Update Step 4 loop card calculation

In the Step 4 block inside `_build_4100es_products()`, add a check before the device-division formula:

**Before:**
```python
qty_loop = math.ceil(total_devices / loop_per) if total_devices else 0
```

**After:**
```python
if loop_card_override is not None:
    qty_loop = loop_card_override
else:
    qty_loop = math.ceil(total_devices / loop_per) if total_devices else 0
```

When `loop_card_override` is provided, use it directly. Otherwise fall back to the device-division formula. Since only the multi-panel call site passes this parameter, the single-panel path always gets `None` (the default) and uses the legacy formula.

### 3. Multi-panel path: pass group's loop count from `_run_multi_group()`

In `_run_multi_group()`, at the 4100ES main panel call to `_build_4100es_products()`, add:

```python
main_products = await self._build_4100es_products(
    ...
    nac_override_loops=main_group["loop_count"],
    loop_card_override=main_group["loop_count"],    # NEW
)
```

### 4. Single-panel path: DO NOT pass `loop_card_override`

In `_run_4100es()`, the call to `_build_4100es_products()` does **NOT** pass `loop_card_override`. It remains omitted so the default `None` is used and the legacy device-division formula runs unchanged.

---

## Behavior Summary

| Scenario | Loop card qty |
|---|---|
| Single-panel 4100ES (any Q21 value) | `ceil(devices / 150 or 200)` — **legacy, unchanged** |
| Multi-panel 4100ES main (e.g. 12 loops) | **12** (exact from group's `loop_count`) |
| 4007 / 4010 (any path) | No change |

---

## Files Modified

| File | Change |
|---|---|
| `backend/app/modules/panel_selection/service.py` | Add `loop_card_override` param to `_build_4100es_products()`, use it in Step 4 logic, pass **only** from `_run_multi_group()` call site |

No migrations, no seeds, no frontend changes. Single file edit.

---

## Edge Cases

1. **Single-panel path is completely unaffected:** `loop_card_override` defaults to `None`, so `_build_4100es_products()` always uses `ceil(devices / loop_per)` in this path.

2. **Multi-panel main group has `loop_count` from panel group detection:** Directly used as `loop_card_override` — same value already used for `nac_override_loops`.

3. **`loop_card_override=0`:** `qty_loop = 0` means no loop cards are added. This shouldn't happen in practice since multi-panel groups always have loop_count >= 1.

---

## Relationship to Other Enhancements

- **`multi_panel_loop_groups.md`** — The multi-panel path already passes `nac_override_loops=main_group["loop_count"]` for NAC card calculation. This enhancement adds the analogous `loop_card_override` for loop card calculation. Both are multi-panel-only overrides.
