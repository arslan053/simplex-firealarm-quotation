# 4007 Panel Selection — Implementation Spec

## Overview

The 4007 Panel Selection module determines whether a project uses a Simplex 4007-ES panel and, if so, computes the exact list of products (panel base unit + child cards) with quantities. This runs **after** device selection is complete, at the **project level** (not per-BOQ-item).

---

## 1. Gate Condition

Three conditions must ALL be true for the project to qualify as a 4007 panel:

| Gate | Source | Condition |
|------|--------|-----------|
| Q1 | Computed | **Devices per panel** < 250 |
| Q2 | LLM answer | "Does the BOQ require speakers or amplifiers?" → must be **No** |
| Q3 | LLM answer | "Does the BOQ require telephone jacks or FFT (Firefighter Telephone)?" → must be **No** |

- **Q1** is computed as **devices_per_panel**:
  1. Sum total detection device quantities from `boq_device_selections` (where selectable category is `mx_detection_device` or `idnet_detection_device`).
  2. Check panel analysis answers (Q101/Q102 from `Panel_selection` category). If Q101 or Q102 = "Yes" (multi-panel project), count BOQ items with `category = 'panel'` to get `panel_count`.
  3. `devices_per_panel = total_devices // panel_count` (if multi-panel), or `total_devices` (if single panel / Q103).
  4. Gate passes if `devices_per_panel < 250`.
- **Q2** and **Q3** are answered by the LLM using ALL BOQ items + spec text.

**If ANY gate fails** → result is "Not a 4007 panel" → no products are computed, and this result is shown to the user. No further questions are evaluated.

---

## 2. Questions to Seed (LLM-Answered)

Only questions that require LLM analysis are seeded into `prompt_questions`. Deterministic questions (Q1, Q4–Q13) are computed in code and are NOT seeded.

**Category:** `4007_panel_questions`

| Q# | Question Text | Purpose |
|----|---------------|---------|
| Q2 | Does the BOQ require speakers, amplifiers, or audio notification devices? | Gate — speakers disqualify 4007 |
| Q3 | Does the BOQ require telephone jacks, FFT (Firefighter Telephone), or fire warden intercom? | Gate — telephone disqualifies 4007 |
| Q14 | Does the BOQ mention a printer or require printing capability? | Child card — printer card (only if no workstation) |
| Q17 | Does the BOQ mention a repeater panel, remote annunciator, or LCD annunciator? | Child card — serial annunciator port |
| Q18 | Does the BOQ mention a graphic annunciator, mimic panel, or mimic display? | Child card — mimic/graphic interface |
| Q20 | Does the BOQ mention a panel-mounted annunciator, built-in annunciator, or door-mounted annunciator? | Child card — annunciator card |

**Total:** 6 questions seeded.

> **Note:** Q15 (wired networking), Q16 (fiber networking), and Q19 (IP networking) have been **removed** from
> the child card selection flow. Networking cards are now selected based on `project.network_type` — a project-level
> field set during device selection. This ensures the panel's networking cards match the workstation variant and
> avoids conflicting decisions between the LLM and the device selection pipeline.
> Q15/Q16/Q19 still exist in the DB but their answers are no longer used for product selection.

---

## 3. Deterministic Product Selection (Q4–Q13)

These are evaluated in code using two inputs:
1. **Protocol** — from existing analysis answers (Q1/Q3/Q4 in `Protocol_decision` category → MX or IDNET)
2. **Notification type** — from the `notification_protocol` stored in `boq_device_selections` or determined by checking which notification selectable categories were matched

### Panel Base Unit Matrix (Q4–Q11)

| Protocol | Notification Type | Product Code | Question |
|----------|------------------|--------------|----------|
| MX | Non-addressable (conventional) | 4007-9301 | Q4+Q5 |
| MX | Addressable | 4007-9401 | Q6+Q7 |
| IDNET | Non-addressable (conventional) | 4007-9101 | Q8+Q9 |
| IDNET | Addressable | 4007-9201 | Q10+Q11 |

**Result:** Exactly ONE base unit product code. **Quantity = number of panels** (from panel analysis). Single panel → qty 1.

### Assistive Card Matrix (Q12–Q13)

Only applies when **devices per panel** is between 100 and 250:

| Protocol | Condition | Product Code | Qty per panel |
|----------|-----------|--------------|---------------|
| IDNET | 100 ≤ devices_per_panel ≤ 250 | 4007-9803 | 2 |
| MX | 100 ≤ devices_per_panel ≤ 250 | 4007-6312 | 2 |

**Total quantity = qty_per_panel × number_of_panels.** If devices_per_panel < 100, no assistive card is added.

---

## 4. Child Cards (LLM + Data-Driven)

### 4a. LLM-Driven Child Cards (Q17, Q18, Q20)

For each LLM question answered **"Yes"**, add the corresponding product(s).

**All quantities are PER PANEL.** Total quantity = qty_per_panel × number_of_panels.

| Q# | Product Code | Qty/panel | Product Description |
|----|-------------|-----------|---------------------|
| **Q17 — Repeater/LCD Annunciator** | | | |
| | 4606-9202 | 1 | 4007ES LCD Annunciator — RED |
| | 2975-9461 | 1 | RED Surface Box for 4606-9202 |
| **Q18 — Mimic/Graphic Annunciator** | | | |
| | 4100-7402 | 1 | 64/64 LED/SW Controller Module |
| | 4100-7403 | 1 | 32 Point LED Driver Module |
| | 4100-7404 | 1 | 32 Point Switch Input Module |
| **Q20 — Panel-Mounted Annunciator** | | | |
| | 4007-9805 | 1 | LED Module for 4007 Door Panel |

If a question answer is **"No"** → none of its products are added.

### 4b. Networking Cards (from `project.network_type`)

Networking cards are **no longer driven by LLM questions Q15/Q16/Q19**. Instead, the system
reads `project.network_type` — a field set during device selection based on BOQ + spec analysis.

- If `project.network_type` is `NULL` → no networking needed → skip entirely.
- If set, select cards based on the type:

| network_type | Product Code | Qty/panel | Product Description |
|---|-------------|-----------|---------------------|
| **wired** | 4007-9810 | 1 | 4007ES Modular NIC |
| | 4007-9813 | 2 | Wired Network Media Card |
| **fiber** | 4007-9810 | 1 | 4007ES Modular NIC |
| | 4007-6301 | 1 | 4120 SM-L Duplex Fiber Media |
| | 4007-6302 | 1 | 4120 SM-R Duplex Fiber Media |
| **IP** | 4007-2504 | 1 | CS Gateway w/IP COM 4007ES |

### 4c. Printer Card (Q14 + workstation check)

The printer card is added only when **both** conditions are true:
1. Q14 (LLM answer) = "Yes" — BOQ/spec mentions a printer
2. No workstation exists in the project (no BOQ item matched to a selectable with `subcategory = 'work_station'`)

If a workstation is present, it handles printing — the panel does not need its own printer interface card.

| Condition | Product Code | Qty/panel | Product Description |
|---|-------------|-----------|---------------------|
| Q14=Yes AND no workstation | 4007-9812 | 1 | Dual RS232 Module (Printer Connection) |

### Quantity Calculation Rule

**Every product quantity is per-panel.** The final quantity stored is:

```
final_qty = qty_per_panel × number_of_panels
```

Where `number_of_panels` comes from the panel analysis (Q101/Q102 multi-panel → count BOQ items with category 'panel'; Q103 single panel → 1).

---

## 5. Database Schema

### New Table: `panel_selections`

```sql
CREATE TABLE panel_selections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    project_id      UUID NOT NULL REFERENCES projects(id),
    product_code    VARCHAR(20) NOT NULL,
    product_name    TEXT,
    quantity        INTEGER NOT NULL DEFAULT 1,
    source          VARCHAR(50) NOT NULL,   -- 'base_unit', 'assistive_card', 'child_card', 'gate_fail'
    question_no     INTEGER,                -- which question triggered this product (NULL for base_unit)
    reason          TEXT,                    -- brief explanation
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_panel_sel_tenant_project ON panel_selections (tenant_id, project_id);
```

- **RLS** enabled with same tenant isolation pattern as other tables.
- **No UNIQUE constraint on product_code** per project — we DELETE + re-INSERT on each run.
- **`source`** column categorizes why the product was added.
- **`question_no`** tracks which question triggered the product (for traceability).

### New Migration: `017_panel_selections.py`

---

## 6. LLM Prompt Design

### System Prompt

```
You are a fire protection system panel configuration expert. Your task is to
analyze the BOQ (Bill of Quantities) and project specification to answer
questions about what panel features and child cards are needed.

## Instructions

For each question, analyze ALL BOQ items and the specification text to
determine if the described feature/device is required.

Answer each question with:
- "Yes" if the BOQ or specification clearly mentions or implies the feature
- "No" if there is no indication the feature is needed

Be thorough — check BOQ item descriptions, quantities, and specification
sections for any mention of the relevant devices or capabilities.

## Output Format

Return ONLY valid JSON (no markdown fences):
{
  "answers": [
    {
      "question_no": <int>,
      "answer": "Yes" or "No",
      "confidence": "High" or "Medium" or "Low",
      "supporting_notes": ["<evidence from BOQ/spec>"],
      "inferred_from": "BOQ" or "Spec" or "Both" or "Neither"
    }
  ]
}

You MUST return an answer for EVERY question provided.
```

### User Message Construction

```
== BOQ Items ==
<JSON array of ALL boq_items: [{id, description, quantity}]>

== Project Specification ==
<spec text from spec_blocks, or "No specification document available.">

== Questions ==
Q2: Does the BOQ require speakers, amplifiers, or audio notification devices?
Q3: Does the BOQ require telephone jacks, FFT (Firefighter Telephone), or fire warden intercom?
Q14: Does the BOQ mention a printer or require printing capability?
...
Q20: Does the BOQ mention a panel-mounted annunciator, built-in annunciator, or door-mounted annunciator?
```

**ALL BOQ items are sent** (not just unmatched ones). This ensures the LLM has full project context.

---

## 7. Service Logic Flow

### `PanelSelectionService.run(tenant_id, project_id)`

```
1. LOAD all BOQ items for the project
2. LOAD spec text (same as device_selection._load_spec_text)
3. LOAD device selection results (for device count + notification type)
4. LOAD protocol from analysis_answers (MX or IDNET)

── Gate Check ──
5. COMPUTE Q1:
   a. total_detection_devices = sum of qty for boq items matched to detection selectables
   b. panel_count = from panel analysis (Q101/Q102 = "Yes" → count BOQ items with category 'panel')
   c. devices_per_panel = total_devices // panel_count (if multi-panel), else total_devices
   - If devices_per_panel >= 250 → gate FAIL
6. LOAD 4007_panel_questions from prompt_questions
7. CALL LLM with ALL BOQ items + spec text + questions (Q2, Q3, Q14-Q20)
8. PARSE LLM response → answers[]
9. STORE answers in analysis_answers table (category: 4007_panel_questions)
10. CHECK Q2 answer → if "Yes" → gate FAIL (speakers required)
11. CHECK Q3 answer → if "Yes" → gate FAIL (telephone required)

── If gate FAILS ──
12. DELETE old panel_selections for this project
13. INSERT single row: source='gate_fail', reason='<which gate failed>'
14. RETURN result with is_4007_panel=false

── If gate PASSES ──
15. DELETE old panel_selections for this project
16. SET num_panels = panel_count (from step 5b) or 1 if single panel
17. DETERMINE base unit from protocol × notification_type matrix → INSERT with qty = num_panels
18. CHECK assistive card (100 ≤ devices_per_panel ≤ 250) → INSERT with qty = 2 × num_panels
19. FOR each Q14-Q20: if answer="Yes" → INSERT each product in that question's list
    with qty = qty_per_panel × num_panels (some questions produce 2-3 products)
20. RETURN result with is_4007_panel=true + products list
```

---

## 8. API Endpoints

### Module: `panel_selection` (NEW — separate from existing `panel_analysis`)

**Prefix:** `/api/projects/{project_id}/panel-selection`

#### POST `/run`
- Starts background job for panel selection
- Returns `{ job_id, status, message }`
- Background job pattern: same as device_selection/spec_analysis

#### GET `/status/{job_id}`
- Poll job status
- Returns `{ job_id, status, message }`

#### GET `/results`
- Returns panel selection results
- Response:
```json
{
  "project_id": "uuid",
  "is_4007_panel": true,
  "gate_result": {
    "q1_total_devices": 540,
    "q1_devices_per_panel": 180,
    "q1_panel_count": 3,
    "q1_passed": true,
    "q2_answer": "No",
    "q2_passed": true,
    "q3_answer": "No",
    "q3_passed": true
  },
  "products": [
    {
      "product_code": "4007-9301",
      "product_name": "4007-9301 panel base",
      "quantity": 3,
      "source": "base_unit",
      "reason": "MX protocol with non_addressable notification"
    },
    {
      "product_code": "4007-6312",
      "product_name": "Assistive SLC Card",
      "quantity": 6,
      "source": "assistive_card",
      "reason": "180 devices per panel (100-250 range), qty 2 x 3 panels"
    },
    {
      "product_code": "4007-9810",
      "product_name": "4007ES Modular NIC",
      "quantity": 3,
      "source": "child_card",
      "question_no": 15,
      "reason": "BOQ mentions copper networking"
    },
    {
      "product_code": "4007-9813",
      "product_name": "Wired Network Media Card",
      "quantity": 6,
      "source": "child_card",
      "question_no": 15,
      "reason": "BOQ mentions copper networking"
    }
  ],
  "status": "success",
  "message": "4007 panel configuration complete. 4 products selected."
}
```

---

## 9. Frontend Component

### `PanelConfigurationSection` (NEW)

**Location:** `frontend/src/features/projects/components/PanelConfigurationSection.tsx`

**Placement:** Below `DeviceSelectionSection` in `ProjectResultsPage.tsx`

#### UI Design

1. **Header row:** "4007 Panel Configuration" title + "Run Panel Selection" button
2. **Status indicators:** Loading spinner, error banner, success banner (same pattern as DeviceSelectionSection)
3. **Gate result display:**
   - If NOT a 4007 panel: Show alert box with reason (e.g., "This project does not qualify for a 4007-ES panel: BOQ requires speakers/amplifiers")
   - If IS a 4007 panel: Show green success badge
4. **Products table** (only shown when is_4007_panel=true):

| Product Code | Description | Qty | Source | Reason |
|-------------|-------------|-----|--------|--------|
| 4007-9301 | 4007-ES Panel — MX, Conventional NAC | 1 | Base Unit | MX protocol with conventional notification |
| 4007-6312 | Assistive SLC Card | 2 | Assistive Card | 180 detection devices (100-250 range) |
| 4007-9810 | Printer Port Card | 1 | Child Card | BOQ mentions printer |

5. **Download CSV** button for the products table

#### API Integration

```typescript
// frontend/src/features/projects/api/panel-selection.api.ts
export const panelSelectionApi = {
  run: (projectId: string) => api.post(`/projects/${projectId}/panel-selection/run`),
  getStatus: (projectId: string, jobId: string) => api.get(`/projects/${projectId}/panel-selection/status/${jobId}`),
  getResults: (projectId: string) => api.get(`/projects/${projectId}/panel-selection/results`),
};
```

#### Types

```typescript
// frontend/src/features/projects/types/panel-selection.ts
export interface PanelSelectionGateResult {
  q1_total_devices: number;
  q1_devices_per_panel: number;
  q1_panel_count: number | null;
  q1_passed: boolean;
  q2_answer: string;
  q2_passed: boolean;
  q3_answer: string;
  q3_passed: boolean;
}

export interface PanelSelectionProduct {
  product_code: string;
  product_name: string | null;
  quantity: number;
  source: string;
  question_no: number | null;
  reason: string | null;
}

export interface PanelSelectionResults {
  project_id: string;
  is_4007_panel: boolean;
  gate_result: PanelSelectionGateResult;
  products: PanelSelectionProduct[];
  status: string;
  message: string;
}

export interface PanelSelectionJobStatus {
  job_id: string;
  status: string;
  message: string;
}
```

---

## 10. Notification Type Determination

To determine the notification type for the base unit matrix, the service checks the device selection results:

1. Query `boq_device_selections` joined with `selectables` where category IN (`addressable_notification_device`, `non_addressable_notification_device`)
2. If ANY matched selectable has category `non_addressable_notification_device` → notification type = **conventional (non-addressable)**
3. If ALL matched notification selectables are `addressable_notification_device` → notification type = **addressable**
4. If NO notification devices matched → default to **conventional (non-addressable)**

---

## 11. File Structure

### New Files

| File | Purpose |
|------|---------|
| `backend/alembic/versions/017_panel_selections.py` | Migration for panel_selections table |
| `backend/seeds/seed_4007_panel_questions.py` | Seed 9 LLM questions |
| `backend/app/modules/panel_selection/__init__.py` | Module init |
| `backend/app/modules/panel_selection/service.py` | Core logic + LLM call |
| `backend/app/modules/panel_selection/router.py` | API endpoints |
| `backend/app/modules/panel_selection/schemas.py` | Pydantic models |
| `frontend/src/features/projects/api/panel-selection.api.ts` | API client |
| `frontend/src/features/projects/types/panel-selection.ts` | TypeScript types |
| `frontend/src/features/projects/components/PanelConfigurationSection.tsx` | UI component |

### Modified Files

| File | Change |
|------|--------|
| `backend/app/main.py` | Register `panel_selection.router` |
| `frontend/src/features/projects/pages/ProjectResultsPage.tsx` | Add `PanelConfigurationSection` below `DeviceSelectionSection` |

---

## 12. Execution Order

1. Write migration `017_panel_selections.py`
2. Run `alembic upgrade head`
3. Write seed script `seed_4007_panel_questions.py`
4. Run seed script
5. Create `panel_selection` module (service, router, schemas)
6. Register router in `main.py`
7. Create frontend files (api, types, component)
8. Add component to `ProjectResultsPage.tsx`
9. Test end-to-end
