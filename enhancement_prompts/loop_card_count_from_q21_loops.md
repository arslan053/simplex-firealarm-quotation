# Enhancement: Use Q21 Loop Count for 4100ES Loop Cards & Multi-Panel Enclosure Override

## Problem Statement

The 4100ES loop card quantity (Step 4 in `_build_4100es_products()`) is calculated by dividing total devices by per-loop capacity:

```python
qty_loop = math.ceil(total_devices / 150)   # MX protocol
qty_loop = math.ceil(total_devices / 200)   # IDNET protocol
```

But when Q21 returns actual loop counts from BOQ panel items (e.g. "11-loop panel"), the loop card count should be **exactly the stated loop count per panel** — not derived from device count. An 11-loop panel needs 11 loop cards **per panel**, so 3 panels × 11 loops = 33 loop cards total.

Additionally, in multi-panel-group mode, the enclosure selection (Step 17) should not use the legacy greedy bin-packing algorithm. Instead, each 4100ES panel gets exactly **1× 3-bay enclosure** (`2975-9443`).

---

## Affected Paths

### Loop Card Override

Applies to **both** 4100ES paths:

| Path | Loop card behavior |
|---|---|
| **Single-panel 4100ES** (`_run_4100es()`) | `loop_count × num_panels` when Q21 provides loops, else legacy formula |
| **Multi-panel-group 4100ES main** (`_run_multi_group()`) | `main_group["loop_count"] × num_panels` |
| **4007 / 4010 (any path)** | **UNCHANGED** — no loop card step |

### Enclosure Override

Applies **only** to multi-panel-group 4100ES:

| Path | Enclosure behavior |
|---|---|
| **Single-panel 4100ES** | **UNCHANGED** — legacy greedy bin-packing from PSU + amplifier count |
| **Multi-panel-group 4100ES main** | **OVERRIDE** — 1× 3-bay enclosure (`2975-9443`) per panel |
| **4007 / 4010 (any path)** | **UNCHANGED** |

---

## Implementation

**File:** `backend/app/modules/panel_selection/service.py`

### 1. Add parameters to `_build_4100es_products()`

Add two new optional parameters alongside the existing `nac_override_loops`:

```python
nac_override_loops: int | None = None,
loop_card_override: int | None = None,
is_multi_panel: bool = False,
```

### 2. Update Step 4 loop card calculation

**Before:**
```python
qty_loop = math.ceil(total_devices / loop_per) if total_devices else 0
```

**After:**
```python
if loop_card_override is not None:
    qty_loop = loop_card_override * num_panels
else:
    qty_loop = math.ceil(total_devices / loop_per) if total_devices else 0
```

`loop_card_override` is the per-panel loop count. Multiply by `num_panels` to get total loop cards. When `None`, falls back to legacy device-division formula.

### 3. Update Step 17 enclosure selection

**Before:**
```python
# ── Step 17: Enclosure (greedy bin-packing) ──
total_slots = qty_psu + qty_std_amp
enclosures = _select_enclosures(qty_psu, qty_std_amp)
for encl_code, encl_qty in enclosures:
    products.append(...)
```

**After:**
```python
# ── Step 17: Enclosure ──
if is_multi_panel:
    # Multi-panel 4100ES: 1× 3-bay enclosure per panel
    products.append(await self._product(
        "2975-9443", num_panels, "step_17_enclosure",
        f"Multi-panel: 1x 3-bay enclosure per panel × {num_panels}",
    ))
else:
    # Legacy: greedy bin-packing based on PSU + amplifier slots
    total_slots = qty_psu + qty_std_amp
    enclosures = _select_enclosures(qty_psu, qty_std_amp)
    for encl_code, encl_qty in enclosures:
        products.append(...)
```

### 4. Single-panel path: pass `loop_count` from `_run_4100es()`

```python
products = await self._build_4100es_products(
    ...
    has_workstation=has_workstation,
    loop_card_override=loop_count,       # per-panel loops from Q21
)
```

`is_multi_panel` is NOT passed — defaults to `False` — so legacy enclosure logic runs.

### 5. Multi-panel path: pass both overrides from `_run_multi_group()`

```python
main_products = await self._build_4100es_products(
    ...
    nac_override_loops=main_group["loop_count"],
    loop_card_override=main_group["loop_count"],
    is_multi_panel=True,
)
```

`is_multi_panel=True` triggers the 3-bay enclosure override in Step 17.

---

## Behavior Summary

| Scenario | Loop cards | Enclosure |
|---|---|---|
| Single-panel 4100ES, Q21 has loops (e.g. 11, 3 panels) | 11 × 3 = **33** | Legacy bin-packing |
| Single-panel 4100ES, Q21 empty | `ceil(devices / 150 or 200)` | Legacy bin-packing |
| Multi-panel 4100ES main (e.g. 12 loops, 6 panels) | 12 × 6 = **72** | 6× 3-bay (`2975-9443`) |
| 4007 / 4010 (any path) | No change | No change |

---

## Files Modified

| File | Change |
|---|---|
| `backend/app/modules/panel_selection/service.py` | Add `loop_card_override` + `is_multi_panel` params, multiply loops × panels in Step 4, 3-bay enclosure override in Step 17, pass from both call sites |

No migrations, no seeds, no frontend changes. Single file edit.

---

## Edge Cases

1. **`loop_count` is `None` from Q21:** `loop_card_override=None` → falls through to legacy `ceil(devices / loop_per)`.

2. **Single-panel with `num_panels=1`:** `loop_count × 1` = same as loop_count. No change in behavior.

3. **Multi-panel enclosure:** Always 1× 3-bay per panel regardless of PSU/amp count. The 3-bay enclosure (`2975-9443`) is the standard full-size enclosure for 4100ES.

---

## Relationship to Other Enhancements

- **`multi_panel_loop_groups.md`** — The multi-panel path already passes `nac_override_loops` for NAC cards. This adds `loop_card_override` for loop cards and `is_multi_panel` for enclosure override. All three are multi-panel-specific overrides to `_build_4100es_products()`.
