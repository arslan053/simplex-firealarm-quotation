# Unified Panel Selection — Implementation Spec

## Overview

The Panel Selection module determines which Simplex fire panel a project requires and computes the exact product list (base unit + optional cards) with quantities. Three panel types are supported:

| Panel Type | Key | Device Range (per panel) | Label |
|---|---|---|---|
| 4007-ES | `4007` | 1 – 249 | "4007-ES" |
| 4010 1-Bay | `4010_1bay` | 250 – 499 | "4010 (1-Bay)" |
| 4010 2-Bay | `4010_2bay` | 500 – 999 | "4010 (2-Bay)" |

If `devices_per_panel >= 1000`, no panel type is supported.

---

## 1. Current State (What Already Exists)

All of the following are **already built and working** for 4007-only:

| Component | Path | Status |
|---|---|---|
| Migration | `backend/alembic/versions/017_panel_selections.py` | Done |
| Seed script | `backend/seeds/seed_4007_panel_questions.py` | Done — 9 questions (Q2, Q3, Q14–Q20). Q15/Q16/Q19 no longer used for product selection |
| Service | `backend/app/modules/panel_selection/service.py` | Needs update |
| Router | `backend/app/modules/panel_selection/router.py` | Needs update |
| Schemas | `backend/app/modules/panel_selection/schemas.py` | Needs update |
| Frontend types | `frontend/src/features/projects/types/panel-selection.ts` | Needs update |
| Frontend component | `frontend/src/features/projects/components/PanelConfigurationSection.tsx` | Needs update |
| Frontend API client | `frontend/src/features/projects/api/panel-selection.api.ts` | No change |
| Router registration | `backend/app/main.py` | No change |
| Results page | `frontend/src/features/projects/pages/ProjectResultsPage.tsx` | Minor comment update |

**No new migration needed.** The `panel_selections` table stores products per project — same table works for all panel types.

**No new seed script needed.** The same LLM questions (Q2, Q3, Q14, Q17, Q18, Q20) apply to all panel types. The only difference is which product codes each answer maps to — that is controlled by the config dict, not the questions.

> **Note:** Q15 (wired networking), Q16 (fiber networking), and Q19 (IP networking) have been **removed** from
> the child card selection flow. Networking cards are now selected based on `project.network_type` — a project-level
> field set during device selection. Q15/Q16/Q19 still exist in the DB but their answers are no longer used for product selection.

---

## 2. Gate Logic (Range-Based Panel Type Selection)

### Step-by-step

```
1. Get protocol (MX or IDNET) from Protocol_decision analysis answers
2. Count total detection devices from boq_device_selections
3. Get panel_count from Panel_selection Q101/Q102 analysis answers
4. Compute: devices_per_panel = total_devices // panel_count (or total_devices if single panel)
5. Determine panel_type from range:
     devices_per_panel < 250      → "4007"
     250 ≤ devices_per_panel < 500 → "4010_1bay"
     500 ≤ devices_per_panel < 1000 → "4010_2bay"
     devices_per_panel >= 1000     → None (gate fail: too many devices)
6. If panel_type is None → GATE FAIL (devices out of range)
7. Get notification_type (addressable or non_addressable) from device selection results
8. If panel_type starts with "4010" AND protocol == "MX" AND notification == "addressable":
     → GATE FAIL: "4010 does not support MX with addressable notification"
9. Call LLM for Q2, Q3, Q14, Q17, Q18, Q20
10. If Q2 == "Yes" → GATE FAIL: speakers/amplifiers required
11. If Q3 == "Yes" → GATE FAIL: telephone/FFT required
12. All gates pass → build product list from PANEL_CONFIGS[panel_type]
    - LLM-driven child cards: Q17, Q18, Q20
    - Networking cards: from project.network_type (not LLM)
    - Printer card: Q14=Yes AND no workstation in project
```

### Gate Summary Table

| Gate | Condition | Applies to |
|---|---|---|
| Device count | `devices_per_panel` must be within a supported range (1–999) | All |
| MX + Addressable block | Protocol=MX AND notification=addressable → fail | 4010 only |
| Q2 — Speakers | LLM answer must be "No" | All |
| Q3 — Telephone/FFT | LLM answer must be "No" | All |

---

## 3. PANEL_CONFIGS — The Config Dict

This single Python dict replaces the current hardcoded `BASE_UNIT_MAP`, `ASSISTIVE_CARD_MAP`, and `CHILD_CARD_MAP`. It lives at the top of `service.py`.

```python
PANEL_CONFIGS: dict[str, dict] = {
    "4007": {
        "label": "4007-ES",
        "range": (0, 250),
        "supports_mx_addressable": True,
        "base_unit_map": {
            ("MX", "non_addressable"):    [("4007-9301", 1)],
            ("MX", "addressable"):        [("4007-9401", 1)],
            ("IDNET", "non_addressable"): [("4007-9101", 1)],
            ("IDNET", "addressable"):     [("4007-9201", 1)],
        },
        "assistive_card": {
            "range": (100, 250),
            "qty_per_panel": 2,
            "map": {
                "IDNET": "4007-9803",
                "MX":    "4007-6312",
            },
        },
        # LLM-driven child cards (Q17/Q18/Q20 only)
        "child_card_map": {
            17: [("4606-9202", 1), ("2975-9461", 1)],
            18: [("4100-7402", 1), ("4100-7403", 1), ("4100-7404", 1)],
            20: [("4007-9805", 1)],
        },
        # Printer card (Q14=Yes AND no workstation)
        "printer_card": [("4007-9812", 1)],
        # Networking cards (from project.network_type, not LLM)
        "networking_map": {
            "wired": [("4007-9810", 1), ("4007-9813", 2)],
            "fiber": [("4007-9810", 1), ("4007-6301", 1), ("4007-6302", 1)],
            "IP":    [("4007-2504", 1)],
        },
    },
    "4010_1bay": {
        "label": "4010 (1-Bay)",
        "range": (250, 500),
        "supports_mx_addressable": False,
        "base_unit_map": {
            ("MX", "non_addressable"):    [("4010-9505", 1), ("4010-6311", 1)],
            ("IDNET", "non_addressable"): [("4010-9501", 1), ("4010-9929", 1)],
            ("IDNET", "addressable"):     [("4010-9701", 1), ("4010-9929", 1)],
        },
        "assistive_card": None,
        "child_card_map": {
            17: [("4606-9102", 1), ("2975-9206", 1)],
            18: [("4100-7402", 1), ("4100-7403", 1), ("4100-7404", 1)],
        },
        "printer_card": [("4010-9918", 1)],
        "networking_map": {
            "wired": [("4010-9922", 1), ("4010-9818", 2)],
            "fiber": [("4010-9922", 1), ("4010-6301", 1), ("4010-6302", 1)],
            "IP":    [("4010-2504", 1)],
        },
    },
    "4010_2bay": {
        "label": "4010 (2-Bay)",
        "range": (500, 1000),
        "supports_mx_addressable": False,
        "base_unit_map": {
            ("MX", "non_addressable"):    [("4010-9523", 1), ("4010-6311", 2)],
            ("IDNET", "non_addressable"): [("4010-9521", 1), ("4010-9929", 2)],
            ("IDNET", "addressable"):     [("4010-9721", 1), ("4010-9929", 2)],
        },
        "assistive_card": None,
        "child_card_map": {
            17: [("4606-9102", 1), ("2975-9206", 1)],
            18: [("4100-7402", 1), ("4100-7403", 1), ("4100-7404", 1)],
        },
        "printer_card": [("4010-9918", 1)],
        "networking_map": {
            "wired": [("4010-9922", 1), ("4010-9818", 2)],
            "fiber": [("4010-9922", 1), ("4010-6301", 1), ("4010-6302", 1)],
            "IP":    [("4010-2504", 1)],
        },
    },
}
```

### Key Differences Between Panel Types

| Feature | 4007 | 4010 1-Bay | 4010 2-Bay |
|---|---|---|---|
| MX + Addressable | Supported | **NOT supported** | **NOT supported** |
| Assistive card | Yes (100–250 range) | No | No |
| Base unit products | 1 product | 2 products | 2 products |
| Base companion qty | — | 1 | **2** |
| Q20 (annunciator) | Yes | No | No |
| LLM child cards | Q17, Q18, Q20 | Q17, Q18 | Q17, Q18 |
| Networking source | `project.network_type` | `project.network_type` | `project.network_type` |
| Printer condition | Q14=Yes AND no workstation | Q14=Yes AND no workstation | Q14=Yes AND no workstation |

---

## 4. Product Building Logic (Pseudo-code)

```python
config = PANEL_CONFIGS[panel_type]
num_panels = panel_count or 1
products = []

# ── Base unit ──
base_products = config["base_unit_map"].get((protocol, notification_type))
# base_products is a list of (code, qty_per_panel)
for code, qty_pp in base_products:
    products.append(code=code, qty=qty_pp * num_panels, source="base_unit")

# ── Assistive card (4007 only) ──
if config["assistive_card"]:
    ac = config["assistive_card"]
    lo, hi = ac["range"]
    if lo <= devices_per_panel <= hi:
        ac_code = ac["map"].get(protocol)
        products.append(code=ac_code, qty=ac["qty_per_panel"] * num_panels, source="assistive_card")

# ── LLM-driven child cards (Q17, Q18, Q20) ──
for qno, card_list in config["child_card_map"].items():
    if llm_answer_map.get(qno) == "Yes":
        for code, qty_pp in card_list:
            products.append(code=code, qty=qty_pp * num_panels, source="child_card", question_no=qno)

# ── Networking cards (from project.network_type) ──
network_type = project.network_type   # set during device selection
if network_type:                       # NULL = no networking needed
    net_cards = config["networking_map"].get(network_type, [])
    for code, qty_pp in net_cards:
        products.append(code=code, qty=qty_pp * num_panels, source="child_card",
                        reason=f"Networking: project network_type={network_type}")

# ── Printer card (Q14 + workstation check) ──
printer = llm_answer_map.get(14) == "Yes"
if printer:
    has_workstation = any BOQ selection with selectable.subcategory == "work_station"
    if not has_workstation:
        for code, qty_pp in config["printer_card"]:
            products.append(code=code, qty=qty_pp * num_panels, source="child_card",
                            reason="Printer required per BOQ/spec (no workstation)", question_no=14)
```

Every quantity is **per-panel** in the config. Final stored quantity = `qty_per_panel * num_panels`.

### Networking vs Printer — Key Points

- **Networking** is NOT an LLM decision. It reads `project.network_type` which was set during device selection based on BOQ + spec analysis (see `workstation_networking_type_detection.md`). If `network_type` is `NULL`, no networking cards are added.
- **Printer** still uses the LLM answer (Q14), but has an additional guard: if a workstation exists in the project (any BOQ item matched to a selectable with `subcategory = 'work_station'`), the printer card is skipped because the workstation handles printing.
- Q15/Q16/Q19 are **retained in the DB** but their answers are no longer used for product selection in any panel type.

---

## 5. Schema Changes

### `schemas.py` — GateResult

Add three new fields:

```python
class GateResult(BaseModel):
    q1_total_devices: int
    q1_devices_per_panel: int
    q1_panel_count: int | None = None
    q1_passed: bool                      # True if devices_per_panel is in ANY supported range
    panel_type: str | None = None        # NEW: "4007", "4010_1bay", "4010_2bay", or None
    panel_label: str | None = None       # NEW: "4007-ES", "4010 (1-Bay)", "4010 (2-Bay)", or None
    mx_addressable_blocked: bool = False # NEW: True if 4010 + MX + addressable
    q2_answer: str | None = None
    q2_passed: bool
    q3_answer: str | None = None
    q3_passed: bool
```

### `schemas.py` — PanelSelectionResultsResponse

Rename `is_4007_panel` → `panel_supported`:

```python
class PanelSelectionResultsResponse(BaseModel):
    project_id: UUID
    panel_supported: bool               # RENAMED from is_4007_panel
    gate_result: GateResult
    products: list[PanelProduct]
    status: str
    message: str
```

---

## 6. Router Changes (`router.py`)

### `_build_gate_result()`

Update to compute `panel_type` from the device range:

```python
def _determine_panel_type(devices_per_panel: int) -> tuple[str | None, str | None]:
    for key, cfg in PANEL_CONFIGS.items():
        lo, hi = cfg["range"]
        if lo <= devices_per_panel < hi:
            return key, cfg["label"]
    return None, None
```

Add `panel_type`, `panel_label`, `mx_addressable_blocked` to the returned `GateResult`.

Update `q1_passed` logic: `q1_passed = panel_type is not None` (instead of `< 250`).

### `get_results()`

- Replace `is_4007_panel=True/False` with `panel_supported=True/False`.
- Update messages from "4007 panel" → dynamic label (e.g., "4010 (1-Bay) panel configuration complete").
- For gate fail: update message from "Not a 4007 panel" → "Panel not supported" or specific reason.

### `_run_background()`

Update status message from "Analyzing BOQ for 4007 panel configuration..." → "Analyzing BOQ for panel configuration...".

---

## 7. Frontend Changes

### `panel-selection.ts` — Types

```typescript
export interface PanelSelectionGateResult {
  q1_total_devices: number;
  q1_devices_per_panel: number;
  q1_panel_count: number | null;
  q1_passed: boolean;
  panel_type: string | null;        // NEW
  panel_label: string | null;       // NEW
  mx_addressable_blocked: boolean;  // NEW
  q2_answer: string | null;
  q2_passed: boolean;
  q3_answer: string | null;
  q3_passed: boolean;
}

export interface PanelSelectionResults {
  project_id: string;
  panel_supported: boolean;          // RENAMED from is_4007_panel
  gate_result: PanelSelectionGateResult;
  products: PanelSelectionProduct[];
  status: string;
  message: string;
}
```

### `PanelConfigurationSection.tsx`

1. **Title**: Change from "4007 Panel Configuration" → "Panel Configuration"
2. **Subtitle**: Change from "Determine panel base unit and child cards from BOQ analysis" → "Determine panel type, base unit and child cards from BOQ analysis"
3. **Gate result display (fail path)**:
   - Show the specific failure reason from `results.message`
   - If `mx_addressable_blocked` is true, show extra line: "4010 does not support MX protocol with addressable notification"
4. **Gate result display (success path)**:
   - Show panel type badge: `results.gate_result.panel_label` (e.g., "4010 (1-Bay)")
   - Change success message to include panel label
5. **Replace all `is4007` / `is_4007_panel` references with `panel_supported`**
6. **CSV download filename**: Change from "4007-panel-configuration.csv" → "panel-configuration.csv"
7. **Empty state text**: Change "4007-ES" references to generic "panel"

### `ProjectResultsPage.tsx`

Update comment from `{/* 4007 Panel Configuration */}` → `{/* Panel Configuration */}`.

---

## 8. File-by-File Change Summary

| # | File | What Changes |
|---|---|---|
| 1 | `backend/app/modules/panel_selection/service.py` | Replace `BASE_UNIT_MAP` / `ASSISTIVE_CARD_MAP` / `CHILD_CARD_MAP` with `PANEL_CONFIGS` dict. Change Q1 gate from `< 250` to range-based `_determine_panel_type()`. Add MX+addressable check for 4010. Update product building loop to read from config. Update `_store_gate_fail` reason messages. Update return dict keys: `is_4007_panel` → `panel_supported`, add `panel_type`/`panel_label`. |
| 2 | `backend/app/modules/panel_selection/schemas.py` | Add `panel_type`, `panel_label`, `mx_addressable_blocked` to `GateResult`. Rename `is_4007_panel` → `panel_supported` in `PanelSelectionResultsResponse`. |
| 3 | `backend/app/modules/panel_selection/router.py` | Import `PANEL_CONFIGS` from service. Update `_build_gate_result()` to compute `panel_type` from range. Update `get_results()` response to use `panel_supported` and dynamic messages. Update background message to be generic. |
| 4 | `frontend/src/features/projects/types/panel-selection.ts` | Add `panel_type`, `panel_label`, `mx_addressable_blocked` to `PanelSelectionGateResult`. Rename `is_4007_panel` → `panel_supported`. |
| 5 | `frontend/src/features/projects/components/PanelConfigurationSection.tsx` | Update title/subtitle. Replace `is4007` with `panelSupported`. Show panel type label. Update gate display for MX+addressable. Update CSV filename. Update empty state text. |
| 6 | `frontend/src/features/projects/pages/ProjectResultsPage.tsx` | Update comment only. |

### Files NOT Changed

- `backend/alembic/versions/017_panel_selections.py` — no migration needed
- `backend/seeds/seed_4007_panel_questions.py` — same questions for all panels
- `frontend/src/features/projects/api/panel-selection.api.ts` — same API endpoints
- `backend/app/main.py` — router already registered

---

## 9. Execution Order

1. Update `backend/app/modules/panel_selection/schemas.py`
2. Update `backend/app/modules/panel_selection/service.py`
3. Update `backend/app/modules/panel_selection/router.py`
4. Update `frontend/src/features/projects/types/panel-selection.ts`
5. Update `frontend/src/features/projects/components/PanelConfigurationSection.tsx`
6. Update `frontend/src/features/projects/pages/ProjectResultsPage.tsx`
7. Verify: start backend, check no import errors
8. Verify: start frontend, check no TypeScript errors

---

## 10. Product Codes Reference

### 4007-ES Base Units

| Protocol | Notification | Code |
|---|---|---|
| MX | Non-addressable | 4007-9301 |
| MX | Addressable | 4007-9401 |
| IDNET | Non-addressable | 4007-9101 |
| IDNET | Addressable | 4007-9201 |

### 4010 1-Bay Base Units (each row = 2 products)

| Protocol | Notification | Panel Code | Companion Code | Companion Qty |
|---|---|---|---|---|
| MX | Non-addressable | 4010-9505 | 4010-6311 | 1 |
| IDNET | Non-addressable | 4010-9501 | 4010-9929 | 1 |
| IDNET | Addressable | 4010-9701 | 4010-9929 | 1 |
| MX | Addressable | **NOT SUPPORTED** | — | — |

### 4010 2-Bay Base Units (each row = 2 products)

| Protocol | Notification | Panel Code | Companion Code | Companion Qty |
|---|---|---|---|---|
| MX | Non-addressable | 4010-9523 | 4010-6311 | **2** |
| IDNET | Non-addressable | 4010-9521 | 4010-9929 | **2** |
| IDNET | Addressable | 4010-9721 | 4010-9929 | **2** |
| MX | Addressable | **NOT SUPPORTED** | — | — |

### 4007 Assistive Cards (100–250 devices/panel only)

| Protocol | Code | Qty/panel |
|---|---|---|
| IDNET | 4007-9803 | 2 |
| MX | 4007-6312 | 2 |

### 4007 LLM-Driven Child Cards (Q17, Q18, Q20)

| Q# | Feature | Code(s) | Qty/panel |
|---|---|---|---|
| 17 | Repeater/LCD | 4606-9202 (1), 2975-9461 (1) | — |
| 18 | Mimic/Graphic | 4100-7402 (1), 4100-7403 (1), 4100-7404 (1) | — |
| 20 | Panel annunciator | 4007-9805 | 1 |

### 4007 Printer Card (Q14 + workstation check)

| Condition | Code | Qty/panel |
|---|---|---|
| Q14=Yes AND no workstation | 4007-9812 | 1 |

### 4007 Networking Cards (from `project.network_type`)

| network_type | Code(s) | Qty/panel |
|---|---|---|
| wired | 4007-9810 (1), 4007-9813 (2) | — |
| fiber | 4007-9810 (1), 4007-6301 (1), 4007-6302 (1) | — |
| IP | 4007-2504 (1) | — |

### 4010 LLM-Driven Child Cards (Q17, Q18 — no Q20)

| Q# | Feature | Code(s) | Qty/panel |
|---|---|---|---|
| 17 | Repeater/LCD | 4606-9102 (1), 2975-9206 (1) | — |
| 18 | Mimic/Graphic | 4100-7402 (1), 4100-7403 (1), 4100-7404 (1) | — |

### 4010 Printer Card (Q14 + workstation check)

| Condition | Code | Qty/panel |
|---|---|---|
| Q14=Yes AND no workstation | 4010-9918 | 1 |

### 4010 Networking Cards (from `project.network_type`)

| network_type | Code(s) | Qty/panel |
|---|---|---|
| wired | 4010-9922 (1), 4010-9818 (2) | — |
| fiber | 4010-9922 (1), 4010-6301 (1), 4010-6302 (1) | — |
| IP | 4010-2504 (1) | — |

LLM child cards, printer card, and networking cards are **identical** between 4010 1-bay and 4010 2-bay.

---

## 11. Note: Missing Product

Product code `4010-9523` (4010 2-Bay MX non-addressable base unit) is not yet in the `products` table. The system will still work — the product name will show as `null` in the UI. Consider adding it to the products seed data when available.
