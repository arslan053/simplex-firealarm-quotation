# Module: Quotation Notes & Inclusions

First read and follow `./prompts/workflow_orchestration.md` — treat it as **mandatory operating rules** for this session. Follow existing repo architecture patterns. Do NOT modify unrelated modules. Keep changes minimal and consistent with repo conventions.

---

## Overview

Enhance the existing quotation generation system with a dynamic **Notes & Inclusions** section. Currently, the quotation DOCX has hardcoded exclusion items that only appear for service options 2/3. This module replaces that with a **registry-based system** where:

- Every service option (1, 2, 3) gets a "NOTES & EXCLUSIONS" section in the document
- Some items are **always included** (defaults) — no user interaction needed
- Some items are **conditionally included** based on **user answers** (Yes/No toggles)
- Some items are **auto-detected** from the project's finalized device selections (e.g., if a workstation selectable is selected, the "Workstation is included" note appears automatically)
- Items **stack by service option**: Option 1 has a base set → Option 2 adds installation-specific items → Option 3 adds even more
- If a conditional item's answer is `false` or missing, it is **silently skipped** (not shown in the document)

### Reference File

`./Questions and Answers for inclusions.xlsx` — Contains the full list of inclusion items with their text and whether they are "Default" or "Based on Offer / User Reply". This file currently covers Options 1 and 2. Option 3 items will be added later. The system must be designed to easily accommodate new items.

---

## Current System (What Exists Now)

### Quotation Module Structure
```
backend/app/modules/quotation/
├── __init__.py
├── models.py          # Quotation SQLAlchemy model
├── schemas.py         # Pydantic request/response schemas
├── router.py          # API endpoints
├── service.py         # Business logic + DOCX generation orchestration
├── generator.py       # DOCX template builder
└── templates/         # Images for header/footer/signature
```

### Current Behavior in generator.py

- **Option 1**: Calls `_add_exclusions(doc, 1)` — renders 7 hardcoded exclusion items as a numbered list
- **Options 2/3**: Calls `_add_notes_exclusions(doc)` — renders 9 hardcoded items in a 2-column table (number | text)
- The `_add_exclusions` function has dead code for options 2/3 that never executes

### Current Document Flow (generator.py → `generate_quotation()`)

```
Option 1:                          Options 2/3:
─────────                          ────────────
_add_client_and_date               _add_client_and_date
_add_subject                       _add_subject
_add_greeting                      _add_greeting
_add_intro                         _add_intro_installation
_add_scope(1)                      _add_scope(2 or 3)
_add_exclusions(1)     ← REMOVE    body text (design change)
_add_warranty          ← KEEP      _add_warranty_short      ← KEEP

── Common for all ──               ── Common for all ──
_add_cancellation                  _add_cancellation
_add_limitation                    _add_limitation
                                   _add_notes_exclusions    ← REMOVE
_add_prices_and_terms              _add_prices_and_terms
_add_payment_terms                 _add_payment_terms
_add_time_for_supplies             _add_time_for_supplies
_add_validity_signature            _add_validity_signature
_add_product_table                 _add_product_table
```

### What Changes

1. **Remove** `_add_exclusions()` function entirely (dead code for options 2/3, replaced for option 1)
2. **Keep the existing `_add_notes_exclusions()` table rendering code exactly as-is** — same 2-column table layout, same column widths (`col_num_w = Cm(0.8)`, `table_width = 85% of content width`), same fixed table layout, same cell padding, same font (`Verdana`, `Pt(9)`), same vertical centering, same `"Table Grid"` style. The ONLY change is: instead of iterating over a hardcoded `items` list, it iterates over the dynamic list returned by `build_document_items()`. Copy/reuse the existing table construction code character-for-character — do NOT rewrite or simplify it.
3. **Move** the notes & exclusions call to the **common section** (after limitation of liability, before prices and terms) so ALL options get it. Previously only options 2/3 called it.
4. The `_add_notes_exclusions()` function signature changes to accept `data: QuotationData` so it can read `service_option` and `inclusion_answers` from the data object.

---

## The Inclusion Registry — `backend/app/modules/quotation/inclusions.py`

### Design

A single Python file that defines **all possible inclusion items** as a list. Each item is a dataclass:

```python
@dataclass
class InclusionItem:
    key: str                              # Unique identifier (e.g., "bms_integration")
    text: str                             # The sentence printed in the document
    applies_to: list[int]                 # Which service options: [1], [1,2], [1,2,3], [2,3], etc.
    mode: str                             # "default" | "ask_user" | "auto_detect"
    auto_detect_subcategory: str | None   # For auto_detect mode: subcategory value to check in selectables
    group: str | None                     # For mutually exclusive choices (e.g., "warranty" — pick one)
```

### Mode Definitions

| Mode | Meaning | Saved in DB? | Shown to User? |
|------|---------|-------------|----------------|
| `default` | Always included in document. No decision needed. | No | No |
| `ask_user` | User must answer Yes/No via toggle in the modal | Yes | Yes (toggle) |
| `auto_detect` | System checks project data and decides automatically | Yes | Yes (locked toggle, shows "Auto-detected") |

### Group Behavior

Items with the same `group` value are **mutually exclusive** — only one can be `true`. The frontend renders them as **radio buttons** instead of toggles. Example: warranty period (12/24/36 months) — user picks exactly one.

### Complete Registry

Define items in this exact order (order = order in the document). Source: `./Questions and Answers for inclusions.xlsx`

```python
INCLUSIONS: list[InclusionItem] = [
    # ══════════════════════════════════════════════════════════════
    # DEFAULT ITEMS — All service options (always printed, no user input)
    # ══════════════════════════════════════════════════════════════
    InclusionItem(
        key="authorized_distributor",
        text="We Rawabi & Gulf Marvel LTD Co is one of the authorized distributor for Simplex-Fire Alarm System.",
        applies_to=[1, 2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="programming_tc_included",
        text="Programming, Testing & Commissioning is included",
        applies_to=[1, 2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="civil_defence_coordination",
        text="We will be coordinating with MEP Contractor for our presence during testing of Fire Alarm System by Civil Defence Team",
        applies_to=[1, 2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="product_data_sheets",
        text="Product Data Sheets are included as part of Technical Submittal",
        applies_to=[1, 2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="shop_drawings_review",
        text="Shop Drawings to be done by MEP Contractor. We will review the shop drawings and provide stamp on it",
        applies_to=[1, 2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="cause_effect_matrix",
        text="We will be providing Cause & Effect Matrix in coordination with MEP Contractor",
        applies_to=[1, 2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="om_manual",
        text="We will be providing Operation & Maintenance Manual in the later stages of the project",
        applies_to=[1, 2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="mtc_certificates",
        text="We will be providing MTC certificates for the delivered material.",
        applies_to=[1, 2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="ul_certificates",
        text="We will be providing UL certificates as part of Technical Submittal",
        applies_to=[1, 2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="spares_excluded",
        text="Spares quantity is not included as part of this offer. Will be quoted separately if needed",
        applies_to=[1, 2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="training_included",
        text="Training will be provided to the operator - For maximum of 2 days, each day 6 hours are included",
        applies_to=[1, 2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="programming_variation",
        text="Programming will be done as per the approved cause and effect. If any changes are needed later or after handover of the project, this will be treated as variation",
        applies_to=[1, 2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),

    # ══════════════════════════════════════════════════════════════
    # CONDITIONAL ITEMS — User answers or system auto-detects
    # ══════════════════════════════════════════════════════════════
    InclusionItem(
        key="bms_integration",
        text="Bacnet Card for BMS Integration is included",
        applies_to=[1, 2, 3], mode="ask_user",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="printer",
        text="Printer is included",
        applies_to=[1, 2, 3], mode="ask_user",
        auto_detect_subcategory=None, group=None,
        # NOTE: Change mode to "auto_detect" once printer has a subcategory in selectables
    ),
    InclusionItem(
        key="workstation",
        text="Work Station is included in the offer",
        applies_to=[1, 2, 3], mode="auto_detect",
        auto_detect_subcategory="work_station", group=None,
    ),
    InclusionItem(
        key="smoke_management",
        text="Smoke Management System is included on the offer for floor wise activation of Dampers or Group wise activation of FANS",
        applies_to=[1, 2, 3], mode="ask_user",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="network_existing",
        text="Network connection to Existing System is included",
        applies_to=[1, 2, 3], mode="ask_user",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="third_party_interfaces",
        text="Interfaces with 3rd Party Systems are included",
        applies_to=[1, 2, 3], mode="ask_user",
        auto_detect_subcategory=None, group=None,
    ),

    # ── Warranty (mutually exclusive — pick one) ──
    InclusionItem(
        key="warranty_12",
        text="Warranty: 12 Months from Date of supply",
        applies_to=[1, 2, 3], mode="ask_user",
        auto_detect_subcategory=None, group="warranty",
    ),
    InclusionItem(
        key="warranty_24",
        text="Warranty: 24 Months from Date of supply",
        applies_to=[1, 2, 3], mode="ask_user",
        auto_detect_subcategory=None, group="warranty",
    ),
    InclusionItem(
        key="warranty_36",
        text="Warranty: 36 Months from Date of Supply",
        applies_to=[1, 2, 3], mode="ask_user",
        auto_detect_subcategory=None, group="warranty",
    ),

    # ══════════════════════════════════════════════════════════════
    # OPTION 2/3 EXTRAS — Installation-specific defaults
    # ══════════════════════════════════════════════════════════════
    InclusionItem(
        key="cable_supply",
        text="Supply of Cables with B3 or Belden or Equivalent are Considered",
        applies_to=[2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="terminations",
        text="Terminations in our devices will be done by us and 3rd party side terminations will be done by 3rd party with coordination",
        applies_to=[2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="civil_works_excluded",
        text="Civil related works are excluded. If the delay is because of RGM in supply of material or installation or lack of sufficient manpower then we will coordinate through AFET.",
        applies_to=[2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="electrical_power",
        text="All Electrical Power needed for to be provided by Main contractor.",
        applies_to=[2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="material_availability",
        text="Material shall be readily available from RGM and work shall not be stopped by not providing access or any other delay.",
        applies_to=[2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="work_stoppage_charges",
        text="If work is stopped because of non-availability of access to work for 3 times in a row, labour hourly charges shall be charged extra to Main Contractor.",
        applies_to=[2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="installation_payment",
        text="Installation Payment \u2013 As per progress of site \u2013 calculated on per point basis \u2013 payable with current dated cheque immediately after submission of invoice.",
        applies_to=[2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="payment_delay_right",
        text="We reserve the right to stop the work if payment is delayed by more than 10 days\u2019 time",
        applies_to=[2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="daily_work_check",
        text="Work completed shall be checked on daily basis and if anything found not as per approved drawings, we shall be informed immediately. Changes will be done free of cost if our worker did not follow drawings. If any changes pointed out afterwards, it will be charged extra",
        applies_to=[2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),
    InclusionItem(
        key="scaffolding_mep",
        text="Scaffolding / man Lift in High Ceiling areas to be provided by MEP Contractor",
        applies_to=[2, 3], mode="default",
        auto_detect_subcategory=None, group=None,
    ),

    # ══════════════════════════════════════════════════════════════
    # OPTION 3 EXTRAS — Full installation specific (to be added later)
    # ══════════════════════════════════════════════════════════════
    # Add Option 3-only items here when defined.
    # Example:
    # InclusionItem(
    #     key="conduiting_included",
    #     text="Conduiting supply and installation is included",
    #     applies_to=[3], mode="default",
    #     auto_detect_subcategory=None, group=None,
    # ),
]
```

### Helper Functions in inclusions.py

```python
def get_inclusions_for_option(service_option: int) -> list[InclusionItem]:
    """Return all inclusion items applicable to the given service option, in registry order."""
    return [item for item in INCLUSIONS if service_option in item.applies_to]


def get_questions_for_option(service_option: int) -> list[InclusionItem]:
    """Return only the items that need user input or show auto-detected status.
    Excludes 'default' items (they don't need any decision)."""
    return [
        item for item in INCLUSIONS
        if service_option in item.applies_to and item.mode != "default"
    ]


def build_document_items(service_option: int, inclusion_answers: dict) -> list[str]:
    """Build the final ordered list of text strings to render in the document.
    - Default items: always included
    - ask_user / auto_detect items: only if key is True in inclusion_answers
    """
    items = []
    for inc in INCLUSIONS:
        if service_option not in inc.applies_to:
            continue
        if inc.mode == "default":
            items.append(inc.text)
        elif inclusion_answers.get(inc.key) is True:
            items.append(inc.text)
    return items
```

---

## Database Migration

### Migration 035: Add `inclusion_answers` to quotations

```sql
ALTER TABLE quotations ADD COLUMN inclusion_answers JSONB NOT NULL DEFAULT '{}';
```

Downgrade:
```sql
ALTER TABLE quotations DROP COLUMN inclusion_answers;
```

Follow existing migration patterns. Revision `"035"`, down_revision `"034"`.

### What Gets Stored

The `inclusion_answers` column stores a flat JSON object mapping inclusion keys to boolean values. Only keys where the user (or system) made a `true` decision need to be stored. Missing keys = `false` = skip.

```json
{
    "bms_integration": true,
    "workstation": true,
    "warranty_24": true
}
```

This means: BMS is included, workstation is included (auto-detected), warranty is 24 months. Everything else (printer, smoke management, etc.) was answered No or not applicable — silently skipped in the document.

---

## Backend Changes

### 1. New File: `quotation/inclusions.py`

As defined above — the registry + helper functions.

### 2. Schema Changes: `quotation/schemas.py`

Add to `GenerateQuotationRequest`:
```python
inclusion_answers: dict[str, bool] = {}
```

Add new response schema for the inclusions endpoint:
```python
class InclusionQuestionItem(BaseModel):
    key: str
    text: str
    mode: str           # "ask_user" or "auto_detect"
    value: bool | None  # None = user must answer, True/False = pre-filled
    group: str | None   # "warranty" or None


class InclusionQuestionsResponse(BaseModel):
    questions: list[InclusionQuestionItem]
```

Add `inclusion_answers` to `QuotationResponse`:
```python
inclusion_answers: dict[str, bool] = {}
```

### 3. Router Changes: `quotation/router.py`

Add new endpoint **before** the existing routes:

```
GET /api/projects/{project_id}/quotation/inclusions?service_option=1
```

This endpoint:
1. Calls `get_questions_for_option(service_option)` to get the list of non-default items
2. For each `auto_detect` item, queries the database to check if the subcategory exists in finalized selections
3. Returns the list with `value` pre-filled for auto-detect items and `null` for ask_user items

### 4. Service Changes: `quotation/service.py`

**New method** — `get_inclusion_questions()`:
```python
async def get_inclusion_questions(
    self, tenant_id: uuid.UUID, project_id: uuid.UUID, service_option: int
) -> list[dict]:
    questions = get_questions_for_option(service_option)
    result = []
    for q in questions:
        value = None
        if q.mode == "auto_detect" and q.auto_detect_subcategory:
            # Check if any finalized selectable has this subcategory
            row = await self.db.execute(
                text("""
                    SELECT COUNT(*) FROM boq_device_selections bds
                    JOIN selectables s ON s.id = bds.selectable_id
                    WHERE bds.tenant_id = :tid AND bds.project_id = :pid
                      AND bds.status = 'finalized'
                      AND s.subcategory = :subcat
                """),
                {"tid": tenant_id, "pid": project_id, "subcat": q.auto_detect_subcategory},
            )
            count = row.scalar() or 0
            value = count > 0
        result.append({
            "key": q.key,
            "text": q.text,
            "mode": q.mode,
            "value": value,
            "group": q.group,
        })
    return result
```

**Modify `generate()` method:**
- Accept `inclusion_answers` from the request
- Pass it to the generator
- Save it in the quotation DB record

**Modify** the INSERT/UPDATE queries to include `inclusion_answers` (as JSONB).

### 5. Generator Changes: `quotation/generator.py`

**Add `inclusion_answers` to `QuotationData`:**
```python
@dataclass
class QuotationData:
    # ... existing fields ...
    inclusion_answers: dict[str, bool] | None = None
```

**Remove** the `_add_exclusions()` function entirely (lines 297-329 in current generator.py).

**Modify `_add_notes_exclusions()`** — keep the EXACT same table rendering code, only change two things:
1. The function now accepts `(doc, data)` instead of just `(doc)`
2. The hardcoded `items` list is replaced with a call to `build_document_items()`

**CRITICAL — Reuse the existing table code exactly.** The current `_add_notes_exclusions()` function (lines 363-441 in generator.py) has precise table formatting that must be preserved character-for-character:
- `col_num_w = Cm(0.8)`
- `table_width = Emu(int(_CONTENT_WIDTH * 0.85))`
- `col_text_w = Emu(int(table_width) - int(col_num_w))`
- `table.style = "Table Grid"`
- Fixed table layout via `w:tblLayout` with `type="fixed"`
- Cell padding: top=40, bottom=40, left=80, right=80
- Grid column widths set at XML level
- Number cell: centered vertically, centered horizontally, `Verdana` `Pt(9)`
- Text cell: centered vertically, `Verdana` `Pt(9)`

Do NOT rewrite, simplify, or refactor the table rendering. Copy it exactly and only replace the `items` source:

```python
def _add_notes_exclusions(doc: Document, data: QuotationData) -> None:
    from .inclusions import build_document_items

    items = build_document_items(
        data.service_option,
        data.inclusion_answers or {},
    )

    if not items:
        return  # Nothing to render

    # Section heading — same as before
    p = doc.add_paragraph()
    _set_para_spacing(p, before=200, after=60)
    run = p.add_run("NOTES & EXCLUSIONS:")
    _style_run(run, bold=True, underline=True)

    # ── Table rendering — EXACT COPY of existing code ──
    # Keep all of the following UNCHANGED from the current _add_notes_exclusions():
    # - col_num_w, table_width, col_text_w calculations
    # - doc.add_table(rows=len(items), cols=2)
    # - table.alignment, table.style
    # - tbl_layout fixed
    # - tblCellMar padding
    # - tblGrid column widths
    # - row.cells width assignment
    # - Number cell: vertical center, horizontal center, Verdana Pt(9)
    # - Text cell: vertical center, Verdana Pt(9)
    # The ONLY difference: `items` comes from build_document_items() instead of hardcoded list
    # Numbers in left column auto-increment: 1, 2, 3, ... len(items)
    # (same as current code: `run_num = p_num.add_run(str(i + 1))`)
```

**Modify `generate_quotation()` flow:**

```python
def generate_quotation(data: QuotationData) -> bytes:
    doc = Document()
    _setup_page(doc)
    _setup_header(doc)
    _setup_footer(doc)

    _add_client_and_date(doc, data)
    _add_subject(doc, data.subject or f"Fire Alarm System – Simplex- {data.project_name}")
    _add_greeting(doc, data.client_name)

    if data.service_option == 1:
        _add_intro(doc)
        _add_scope(doc, 1)
        _add_warranty(doc)                    # Full warranty for option 1
    else:
        _add_intro_installation(doc)
        _add_scope(doc, data.service_option)
        _add_body_text(doc, "Any changes in architectural design...")
        _add_warranty_short(doc)              # Short warranty for options 2/3

    # Common sections — ALL options
    _add_cancellation(doc)
    _add_limitation_of_liability(doc)
    _add_notes_exclusions(doc, data)          # ← NEW: dynamic, for ALL options
    _add_prices_and_terms(doc)
    _add_payment_terms(doc, data)
    _add_time_for_supplies(doc)
    _add_validity_and_signature(doc)
    _add_product_table(doc, data)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
```

---

## Frontend Changes

### 1. Types: `features/projects/types/quotation.ts`

Add:
```typescript
interface InclusionQuestion {
    key: string;
    text: string;
    mode: 'ask_user' | 'auto_detect';
    value: boolean | null;
    group: string | null;
}

// Add to GenerateQuotationRequest:
inclusion_answers?: Record<string, boolean>;
```

### 2. API: `features/projects/api/quotation.api.ts`

Add:
```typescript
getInclusions: (projectId: string, serviceOption: number) =>
    apiClient.get(`/projects/${projectId}/quotation/inclusions`, {
        params: { service_option: serviceOption }
    }),
```

### 3. QuotationModal.tsx — Add Inclusions Section

**When it loads / when service option changes:**
1. Call `quotationApi.getInclusions(projectId, serviceOption)`
2. Populate the inclusions UI section

**UI layout inside the modal (after existing fields):**

```
── Notes & Inclusions ──────────────────────────────

  BMS Integration (Bacnet Card)              [🔘 toggle]
  Workstation                    Auto-detected ✅  🔒
  Printer                                    [⚪ toggle]
  Smoke Management System                    [⚪ toggle]
  Network to Existing System                 [⚪ toggle]
  3rd Party Interfaces                       [⚪ toggle]

  Warranty Period:
  ○ 12 Months    ● 24 Months    ○ 36 Months

─────────────────────────────────────────────────────
```

**Behavior rules:**
- `mode: "auto_detect"` → toggle is **disabled/locked**, shows the auto-detected value with a visual indicator (lock icon or "Auto-detected from BOQ" label)
- `mode: "ask_user"` → toggle is **interactive**, user switches on/off
- `group: "warranty"` → render as **radio buttons** (mutually exclusive, exactly one must be selected)
- `group: null` → render as **individual toggles**
- When service option changes (e.g., 1 → 2), **re-fetch** the inclusions list. Keep existing answers for items that still appear; new items start as off.
- On form submit, collect all toggle/radio values into `inclusion_answers: { key: true/false }` and send with the generate request
- **Only send keys that are `true`**. Omit false keys entirely (backend treats missing = false).

---

## Auto-Detection Logic

### Current Auto-Detectable Items

| Key | Subcategory Value | How It Works |
|-----|-------------------|-------------|
| `workstation` | `work_station` | If any finalized selectable in the project has `subcategory = 'work_station'`, value = `true` |

### Database Query for Auto-Detection

```sql
SELECT COUNT(*) FROM boq_device_selections bds
JOIN selectables s ON s.id = bds.selectable_id
WHERE bds.tenant_id = :tid AND bds.project_id = :pid
  AND bds.status = 'finalized'
  AND s.subcategory = :subcategory_value
```

If count > 0 → `true`. If count = 0 → `false`.

### Known Subcategory Values in DB

```
flasher, horn, horn_flasher, speaker, speaker_flasher, work_station
```

### Future Auto-Detection (Not Implemented Now)

When subcategories are added to selectables for these items, change their `mode` from `"ask_user"` to `"auto_detect"` and set `auto_detect_subcategory`:
- `printer` — currently `ask_user`, will become `auto_detect` when a printer subcategory exists
- `bms_integration` — currently `ask_user`, could become `auto_detect` if a BACnet card subcategory is added
- Others as needed

This requires only a change in the `INCLUSIONS` registry (one line per item) — no migration, no frontend change, no new endpoint.

---

## Files Summary

### New Files
| File | Purpose |
|------|---------|
| `backend/app/modules/quotation/inclusions.py` | Inclusion registry + helper functions |
| `backend/alembic/versions/035_add_inclusion_answers.py` | Migration: add JSONB column |

### Modified Files
| File | Change |
|------|--------|
| `backend/app/modules/quotation/schemas.py` | Add `inclusion_answers` to request/response, add `InclusionQuestionItem` + `InclusionQuestionsResponse` |
| `backend/app/modules/quotation/service.py` | Add `get_inclusion_questions()` method, pass `inclusion_answers` through `generate()` |
| `backend/app/modules/quotation/router.py` | Add `GET .../inclusions` endpoint |
| `backend/app/modules/quotation/generator.py` | Remove `_add_exclusions()`, replace `_add_notes_exclusions()` with dynamic version, update `generate_quotation()` flow, add `inclusion_answers` to `QuotationData` |
| `frontend/src/features/projects/types/quotation.ts` | Add `InclusionQuestion` type, add `inclusion_answers` to request |
| `frontend/src/features/projects/api/quotation.api.ts` | Add `getInclusions()` method |
| `frontend/src/features/projects/components/QuotationModal.tsx` | Add inclusions UI section with toggles and radio buttons |

### Files NOT to Modify
- `backend/app/modules/pricing/` — No changes
- `backend/app/modules/boq/` — No changes
- `backend/app/modules/projects/` — No changes
- `backend/app/main.py` — No changes (router already registered)
- Any migration files before 035 — No changes

---

## Implementation Order

1. **Migration 035** — Add `inclusion_answers JSONB` column to `quotations`
2. **`inclusions.py`** — Create the registry file with all items and helper functions
3. **`schemas.py`** — Add new schemas
4. **`service.py`** — Add `get_inclusion_questions()`, modify `generate()` to accept and save `inclusion_answers`
5. **`router.py`** — Add `GET .../inclusions` endpoint
6. **`generator.py`** — Remove old hardcoded functions, add dynamic `_add_notes_exclusions(doc, data)`
7. **Frontend types** — Add `InclusionQuestion`, update `GenerateQuotationRequest`
8. **Frontend API** — Add `getInclusions()`
9. **Frontend QuotationModal** — Add inclusions section with toggles and radio buttons
10. **Test end-to-end** — Generate quotations for each service option, verify correct items appear in DOCX

---

## Verification Checklist

1. Generate quotation with **Option 1** → document has "NOTES & EXCLUSIONS" section with 12 default items + only the conditional items where user said Yes + warranty choice
2. Generate quotation with **Option 2** → same as Option 1 + 10 installation-specific default items appended
3. Generate with **Option 3** → same as Option 2 (until Option 3 extras are defined)
4. Toggle BMS on → "Bacnet Card for BMS Integration is included" appears in document
5. Toggle BMS off → that line does NOT appear in document
6. Workstation auto-detected as `true` (project has work_station selectable) → "Work Station is included" appears, toggle is locked
7. Workstation auto-detected as `false` (no work_station selectable) → line does not appear, toggle shows off and locked
8. Select warranty 24 months → only "Warranty: 24 Months from Date of supply" appears (not 12 or 36)
9. Change service option from 1 to 2 → inclusions list refreshes, installation items appear
10. Re-generate existing quotation → old answers are loaded back into the modal
11. Table in DOCX has correct numbering (1, 2, 3...) matching only the included items
12. Existing quotation fields (client name, address, margin, payment terms) continue to work unchanged

---

## Constraints

- Do NOT create new database tables — only add a column to existing `quotations` table
- Do NOT modify the product table or pricing logic
- Do NOT change the header, footer, signature, or page layout of the DOCX
- Do NOT modify any module outside `quotation/` except frontend files listed above
- Do NOT remove the existing SCOPE or WARRANTY sections — they stay as they are
- The `_add_exclusions()` function is removed but its content is now covered by default items in the registry
- Keep the same 2-column table format (number | text) that currently exists in `_add_notes_exclusions()`
- Follow existing migration patterns: raw SQL, sequential numbering
- Follow existing schema patterns: Pydantic BaseModel
- Follow existing router patterns: tenant isolation, role-based access
