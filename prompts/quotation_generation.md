# Quotation Document Generation Feature

> **Workflow:** Follow `prompts/workflow_orchestration.md` as the main orchestration guide for planning, subagent strategy, verification, and task management while implementing this feature.

## Overview

Implement a professional quotation (offer letter) generation system integrated into the existing RAGM pricing workflow. After a user finalizes pricing with margins, they can generate a formatted `.docx` quotation document that follows the company's exact letterhead template. The document is stored in MinIO and tracked in a dedicated database table.

## Reference Template

The reference template and all extracted assets are at:
```
backend/app/modules/quotation/templates/
├── reference_template.doc          # Original .doc template
├── reference_template.docx         # Converted .docx for parsing
└── images/
    ├── logo.png                    # Gulf Marvel logo (blue square)
    ├── header_text.png             # Arabic + English company name banner
    ├── footer.png                  # Multi-country contact info footer
    └── signature.png               # Mohammed Masood Ali signature
```

**CRITICAL:** Open and visually inspect `reference_template.docx` to understand exact formatting, spacing, fonts, and layout. The generated document must match this template pixel-for-pixel in terms of structure. Use `python-docx` to programmatically read the template and understand its paragraph styles, runs, fonts, table formatting, and image positions before building the generator.

## Template Document Structure (Exact Content)

### Every Page — Header
- **Logo** (`logo.png`): Top-left, approximately 3.0cm wide
- **Header text** (`header_text.png`): Right of logo, right-aligned, approximately 13.5cm wide, Arabic company name + "RAWABI & GULF MARVEL LTD. CO."
- Header table spans full content width (page width minus margins)
- These appear on EVERY page as a repeating header

### Every Page — Footer
- **Footer** (`footer.png`): Full content width (page width minus margins), centered at bottom
- This appears on EVERY page as a repeating footer

### Page 1 — Top Section (Dynamic)
Left-aligned:
```
Engr, [client_name]
[client_address],
Saudi Arabia.
```
Right-aligned:
```
Date: [DD]th [Mon] [YYYY]     ← today's date, ordinal suffix (th/st/nd/rd) must be SUPERSCRIPT
Ref.: MI/203-C/[ref_number]   ← auto-generated reference (format: MI/203-C/{seq}/{year})
```
**IMPORTANT:** The ordinal day suffix ("th", "st", "nd", "rd") must be rendered as superscript text using a separate run with `font.superscript = True`.

### Page 1 — Subject Line (Dynamic)
```
Subject: Fire Alarm System – Simplex- [project_name]
```

### Page 1 — Greeting (Dynamic)
```
Dear Engr, [client_name]
```

### Page 1 — Body Sections (DYNAMIC — depends on service option)

The body sections between the greeting and CANCELLATION differ based on the selected service option.

#### Option 1 — Supply Only (default)

**Introduction:**
```
As requested, please find herewith attached our offer for Fire Alarm System.
```

**SCOPE:**
```
SCOPE
Price includes Supply of equipment mentioned in attached point-schedule, warranty, programming, testing & commissioning.
```

**EXCLUSIONS:**
```
EXCLUSIONS
Following are excluded from our scope and price: -
1. Any kind of civil works
2. Any Kind of Installations or programming
3. Any kind of cables supply and wiring together with allied works such as cable trays, trunking conduiting at field end in panels.
4. Any kind of starters panels, MCC panels.
5. Fittings & fixtures for peripherals, Actuators.
6. Any other item not specifically mentioned by us in this offer.
7. Any cost towards operating the system such as towards an operator for client, etc.
```

**WARRANTY:**
```
WARRANTY:
Items supplied by us shall be covered under our standard warranty clause that covers against any material defect or malfunctioning, for a period of 18 months from date of delivery. Product shall be used as intended. Misuse or wrong application will not be covered under warranty. We also hope that project maintenance will be given to us as a separate contract so that we can maintain the system in a proper way.

However our warranty coverage shall not include wear & tear, consumables, abuse/ misuse/ wrong use of components
```

#### Options 2/3 — Installation Template

**Introduction:**
```
As requested, please find herewith attached our offer for above mentioned systems. The Offer is based on the drawings provided. We have proposed material supply and installation as requested.
```

**SCOPE:** (varies by option — see Service Options section below)

**Design Change Notice:**
```
Any changes in architectural design or material list or system design will change price.
```

**WARRANTY (short):**
```
WARRANTY:
However, our warranty coverage shall not include wear & tear, consumables, abuse/ misuse/ wrong use of components.
```

Then after CANCELLATION and LIMITATION OF LIABILITY (same as option 1):
```
NOTES & EXCLUSIONS:
```
Followed by a 2-column table (number | text) with 9 items:
1. Terminations in our devices will be done by us and 3rd party side terminations will be done by 3rd party with coordination
2. Civil related works are excluded. If the delay is because of RGM in supply of material or installation or lack of sufficient manpower then we will coordinate through AFET.
3. All Electrical Power needed for to be provided by Main contractor.
4. Material shall be readily available from RGM and work shall not be stopped by not providing access or any other delay.
5. If work is stopped because of non-availability of access to work for 3 times in a row, labour hourly charges shall be charged extra to Main Contractor.
6. Installation Payment – As per progress of site – calculated on per point basis – payable with current dated cheque immediately after submission of invoice..
7. We reserve the right to stop the work if payment is delayed by more than 10 days' time
8. Work completed shall be checked on daily basis and if anything found not as per approved drawings, we shall be informed immediately. Changes will be done free of cost if our worker did not follow drawings. If any changes pointed out afterwards, it will be charged extra
9. Scaffolding / man Lift in High Ceiling areas to be provided by MEP Contractor

### Page 1-2 — CANCELLATION (CONSTANT)
```
CANCELLATION:
In case of cancellation of order for whatsoever reasons RGM reserves the right to charge the purchaser for the cost of such cancellations in accordance with the actual stage of processing.
```

### Page 2 — LIMITATION OF LIABILITY (CONSTANT)
```
LIMITATION OF LIABILITY:
The supplier shall not be liable, whether in contract, warranty, failure of remedy to achieve its essential purpose, tort (including negligence or strict liability) indemnity, or any other legal or equitable theory for damage to or loss of other property or equipment, business interruption or lost revenue, profits or sales, cost of capital, or for any special, incidental, punitive, indirect or consequential damages or for any other loss, costs or expenses of similar type.

The liability of the supplier for any act or omission, product sold, serviced or furnished directly or indirectly under this agreement, whether in contract, warranty failure or a remedy to achieve its essential purpose, tort (including negligence or strict liability) indemnity, or any other legal or equitable theory, will in no event exceed 1% of the contract value.

The rights and remedies contained in this agreement are exclusive, and the parties accept these remedies in lieu of all other rights and remedies available at law or otherwise, in contract (including warranty) or in tort (including negligence), for any and all claims of any nature arising under this agreement or any performance or breach arising out of this agreement.
```

### Page 2 — PRICES AND TERMS OF PAYMENT (CONSTANT)
```
PRICES AND TERMS OF PAYMENT:
Without prejudice to any further rights, we may suspend and/ or refuse any supplies for as long as any due payment remains outstanding for whatsoever reason.

Late payments due and payable to supplier shall attract interest at a rated of 12% per annum accruing from their due date until full settlement of the principal amount. Payments by the purchaser shall be deemed to be made first against any accrued interest and then against the outstanding principal amount. The provision of this clause is without prejudice to any further rights of the supplier in case of payment is delayed by the purchaser.
```

### Page 2 — PAYMENT TERMS (DYNAMIC)
```
Payment terms :
  1) 25% Advance with PO.
  2) 70% At time of delivery of material.
  3) 5% After Testing & Commissioning of Fire Alarm System.
```
The payment terms text is stored as a single free-text field (`payment_terms_text`). The frontend provides two modes:

- **Default mode:** The user enters three percentages (Advance / Delivery / Completion) via number inputs. The text is auto-generated from those percentages and shown in a preview. On submit, the generated text is sent as `payment_terms_text`.
- **Custom mode:** The user directly edits the payment terms text in a textarea. On submit, that text is sent as `payment_terms_text`.

In both cases, the backend receives and stores only the final text — no individual percentage columns. The DOCX generator renders each line of `payment_terms_text` as a separate paragraph.

### Page 2 — TIME FOR SUPPLIES (CONSTANT)
```
TIME FOR SUPPLIES:
Delivery – 14 to 16 weeks from the date of advance payment receipt. (Partial Delivery against partial payment allowed)
```

### Page 2 — VALIDITY & SIGNATURE (CONSTANT)
```
Validity – 30 days

Best regards,

[signature.png image here]

Mohammed Masood Ali

+966 55 267 3835
```

### New Page — PRODUCT TABLE (DYNAMIC)
**The product table MUST start on a new page.** Insert an explicit page break (`WD_BREAK.PAGE`) before the table to ensure no blank/empty page appears between the letter content and the product table.

Table with columns: **Model** | **Description** | **Qty** | **Unit Price** | **Total Price**

- Populated from the project's pricing items (after margin is applied)
- Each row: product code, description, quantity, unit price (SAR with margin), total price
- Bottom rows:
  - **TOTAL IN SAR** — sum of all product line totals (subtotal)
  - **Installation Services** (options 2/3 only) — per-device installation charge
  - **VAT** — 15% of (subtotal + installation amount)
  - **GRAND TOTAL IN SAR** — subtotal + installation + VAT

---

## Service Options (3 Types)

The user selects ONE of these when generating the quotation. The selection affects the **entire body template** — Option 1 uses the supply-only template, while Options 2/3 use the installation template (different intro, short warranty, "NOTES & EXCLUSIONS" heading only).

### Installation Services Pricing (Options 2 & 3)

For service options 2 and 3, an **Installation Services** charge is added to the product table based on the number of finalized device selectables in the project:

- **Option 2** (installation without conduiting): `device_count × 480 SAR`
- **Option 3** (full installation with conduiting): `device_count × 680 SAR`
- **Option 1** (supply only): no installation charge

**Device count** = SUM of `boq_items.quantity` for all BOQ items that have a finalized device selection (`boq_device_selections.status = 'finalized'` AND `selectable_id IS NOT NULL`). Panels are excluded (they have `status = 'pending_panel'`).

The installation row appears in the product table between **TOTAL IN SAR** and **VAT**:
```
| Model | Description              | Qty          | Unit Price | Total Price |
|-------|--------------------------|--------------|------------|-------------|
| ...   | (product rows)           | ...          | ...        | ...         |
|       | TOTAL IN SAR             |              |            | [subtotal]  |
|       | Installation Services    | [dev_count]  | [rate]     | [amount]    |
|       | VAT                      |              |            | [vat]       |
|       | GRAND TOTAL IN SAR       |              |            | [grand]     |
```

VAT and grand total include the installation amount:
- `VAT = 15% × (subtotal + installation_amount)`
- `GRAND TOTAL = subtotal + installation_amount + VAT`

### Option 1: Products Supply, Supervision & Programming (DEFAULT)
**Template:** Supply-only (intro → scope → exclusions → full warranty)
**SCOPE text:**
```
Price includes Supply of equipment mentioned in attached point-schedule, warranty, programming, testing & commissioning.
```
**EXCLUSIONS:** All 7 exclusion items listed (installations, cables, conduiting all excluded)

### Option 2: Supply + Installation (no conduiting)
**Template:** Installation (intro → scope → design change notice → short warranty → NOTES & EXCLUSIONS heading)
**SCOPE text:**
```
Price includes Supply of equipment mentioned in attached point-schedule, engineering support which includes preparation of Single Line diagrams, Installation of devices we supplied, cable pulling, device fixing, programming, testing and commissioning of equipment we supplied, Client Staff training, O&M Manuals and Warranty support.
```

### Option 3: Supply + Full Installation (with conduiting)
**Template:** Installation (same as Option 2 but scope includes conduiting)
**SCOPE text:**
```
Price includes Supply of equipment mentioned in attached point-schedule, engineering support which includes preparation of Single Line diagrams, Installation of devices we supplied, conduiting, cable pulling, device fixing, programming, testing and commissioning of equipment we supplied, Client Staff training, O&M Manuals and Warranty support.
```

---

## Reference Number Format

Auto-generated as: `[SEQ]/[YYYY]`

- **SEQ**: Sequential number based on how many projects this user owns up to and including the current project (ordered by `created_at`). Query: `COUNT(*) FROM projects WHERE owner_user_id = :uid AND tenant_id = :tid AND created_at <= (SELECT created_at FROM projects WHERE id = :pid)`
- **YYYY**: Full 4-digit year. E.g., 2026

Example: User's 10th project in 2026 → `10/2026`

In the DOCX document, the reference is displayed as `Ref.: MI/203-C/10/2026` (the `MI/203-C/` prefix is prepended by the generator). The stored `reference_number` in the DB is just `10/2026`.

---

## Database Design

### New Table: `quotations` (Migration 028)

```sql
CREATE TABLE quotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    project_id UUID NOT NULL REFERENCES projects(id),
    generated_by_user_id UUID NOT NULL REFERENCES users(id),

    -- User inputs
    client_name TEXT NOT NULL,
    client_address TEXT NOT NULL,
    service_option INTEGER NOT NULL DEFAULT 1,  -- 1, 2, or 3
    margin_percent NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    payment_terms_text TEXT,              -- free-text payment terms (always stored)

    -- Generated data
    reference_number TEXT NOT NULL,
    subtotal_sar NUMERIC(15,2) NOT NULL,
    vat_sar NUMERIC(15,2) NOT NULL,
    grand_total_sar NUMERIC(15,2) NOT NULL,

    -- File storage
    object_key TEXT NOT NULL,           -- MinIO path
    original_file_name TEXT NOT NULL,   -- e.g., "Quotation_AH-01-03-26.docx"
    file_size BIGINT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One quotation per project (latest replaces previous)
CREATE UNIQUE INDEX uq_quotations_project ON quotations(tenant_id, project_id);

-- RLS
ALTER TABLE quotations ENABLE ROW LEVEL SECURITY;
ALTER TABLE quotations FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_policy ON quotations
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
CREATE POLICY app_bypass_policy ON quotations
    USING (current_setting('app.tenant_id', true) IS NULL);
```

### MinIO Storage Path
```
{tenant_id}/{project_id}/quotations/{uuid}_{filename}.docx
```

Follow the existing patterns in `backend/app/shared/storage.py` for upload, presigned URL generation, and deletion.

---

## Backend Implementation

### Module Structure
```
backend/app/modules/quotation/
├── __init__.py
├── models.py          # Quotation SQLAlchemy model
├── schemas.py         # Pydantic request/response schemas
├── router.py          # API endpoints
├── service.py         # Business logic + document generation
├── generator.py       # DOCX template builder (isolated)
└── templates/
    ├── images/
    │   ├── logo.png
    │   ├── header_text.png
    │   ├── footer.png
    │   └── signature.png
    ├── reference_template.doc
    └── reference_template.docx
```

### Key Library
Use `python-docx` for DOCX generation. Install: `pip install python-docx` and add to `requirements.txt`.

**Do NOT use a Jinja2 template approach.** Build the document programmatically with `python-docx` to have full control over:
- Page headers/footers with images
- Exact font sizes, styles, and spacing
- Table formatting with borders
- Page breaks
- Image positioning

### generator.py — Document Builder

This is the core file. It must:

1. **Read the reference template** (`reference_template.docx`) using `python-docx` to understand exact styles, fonts, paragraph spacing, table cell widths. Match these exactly.

2. **Build the document programmatically:**
   - Set page size to A4, margins matching the template
   - Add header section with logo + header_text images on every page
   - Add footer section with footer image on every page
   - Build all content paragraphs with exact fonts (use the fonts from the reference template)
   - Build the product table with proper borders, column widths, alignment
   - Add signature image at the correct position
   - Handle page breaks naturally (content flows, table spans pages)

3. **Handle the product table robustly:**
   - Table must not break mid-row across pages
   - Column widths: Model (~2.5cm), Description (~6cm), Qty (~2cm), Unit Price (~3cm), Total Price (~3cm)
   - Header row bold with light gray background
   - TOTAL, VAT, GRAND TOTAL rows bold at the bottom
   - Number formatting: prices with commas and 2 decimal places

4. **Return the document as bytes** (in-memory, no temp files).

### API Endpoints

```python
# router.py
prefix = "/api/projects/{project_id}/quotation"

POST /generate          # Generate/regenerate quotation
GET  /                  # Get quotation metadata (if exists)
GET  /download          # Get presigned download URL
```

**POST /generate** — Request body:
```json
{
    "client_name": "Engr. Ali Irfad",
    "client_address": "abc xyz Engineering Co.\nRiyadh",
    "service_option": 1,
    "margin_percent": 15.0,
    "payment_terms_text": "1) 25% Advance with PO.\n2) 70% At time of delivery of material.\n3) 5% After Testing & Commissioning of Fire Alarm System."
}
```

**POST /generate** — Logic:
1. Fetch pricing items for this project (must exist — return 400 if not calculated)
2. Apply margin to each item's unit_cost_sar
3. Generate reference number
4. Build DOCX document via `generator.py` (uses `payment_terms_text` for payment terms section)
6. If a previous quotation exists for this project:
   - Delete the old file from MinIO
   - Update the existing quotation row
7. If no previous quotation:
   - Upload to MinIO
   - Insert new quotation row
8. Return quotation metadata + download URL

**GET /** — Returns quotation metadata if it exists for this project, or 404.

**GET /download** — Returns `{ "url": "<presigned_url>" }` for downloading the DOCX.

### Register Router
Add to `backend/app/main.py`:
```python
from app.modules.quotation.router import router as quotation_router
app.include_router(quotation_router)
```

---

## Frontend Implementation

### 1. Quotation Card on Pricing Page (TOP position)

In `PricingSection.tsx`, the quotation card is shown **at the top of the page** (right after the header bar, before the pricing tables). This ensures the user sees the quotation status immediately.

When a quotation exists, show a card with:
- File name and metadata (ref number, service option, margin, date)
- Three buttons: **Regenerate** | **Show** (opens DOCX in new tab) | **Download**

The header bar also has a "Generate Quotation" / "Regenerate Quotation" button next to the CSV download button.

### 2. Quotation Modal (on "Generate Quotation" click)

A modal/dialog with the form:

**Service Option** (radio buttons):
- ○ Products Supply, Supervision & Programming (Default)
- ○ Full Installation (with conduiting)
- ○ Installation without conduiting

**Client Details:**
- Client Name (text input, prefill from project's `client_name`)
- Client Address (textarea, prefill from project's `city`)

**Payment Terms** (two modes via Default / Custom toggle):
- **Default mode:** Three number inputs (Advance %, Delivery %, Completion %) that must sum to 100. A read-only preview below shows the generated text. On submit, the generated text is sent as `payment_terms_text`.
- **Custom mode:** An editable textarea pre-filled with the generated text (when switching from Default). The user can freely edit the payment terms. On submit, the textarea content is sent as `payment_terms_text`.
- When restoring from an existing quotation, the stored `payment_terms_text` is loaded into the textarea in Custom mode.

**Margin:** (pre-filled from the margin already set on the pricing page — read-only or editable)

**[Generate Quotation]** button

### 3. Auto-Open on Generation

When a quotation is generated (or regenerated), the DOCX automatically opens in a new browser tab via its presigned MinIO URL. This gives instant visual feedback.

### 4. Show Button

The quotation card has a "Show" button (with Eye icon) that opens the presigned DOCX URL in a new browser tab, allowing the user to view/download the file at any time.

### 5. API File

Create `frontend/src/features/projects/api/quotation.api.ts`:
```typescript
export const quotationApi = {
  generate: (projectId: string, data: GenerateQuotationRequest) =>
    apiClient.post(`/projects/${projectId}/quotation/generate`, data),
  get: (projectId: string) =>
    apiClient.get(`/projects/${projectId}/quotation`),
  download: (projectId: string) =>
    apiClient.get(`/projects/${projectId}/quotation/download`),
};
```

### 6. Route Registration

Add to `frontend/src/app/router/index.tsx`:
```typescript
{ path: 'projects/:projectId/quotation', element: <QuotationPage /> }
```

---

## Implementation Workflow

Follow this exact order:

1. **Migration 028** — Create `quotations` table with RLS
2. **Backend model** — `quotation/models.py`
3. **Backend schemas** — Request/response Pydantic models
4. **Backend generator** — `generator.py` — the DOCX builder (most complex part)
5. **Backend service** — Business logic, MinIO integration
6. **Backend router** — API endpoints
7. **Register router** in `main.py`
8. **Add `python-docx`** to `requirements.txt` and rebuild Docker image
9. **Frontend API** — quotation.api.ts
10. **Frontend components** — QuotationModal, QuotationSection in PricingPage
11. **Frontend page** — QuotationPage for viewing/downloading
12. **Frontend routing** — Register new route
13. **Test end-to-end** — Generate a quotation, verify DOCX output matches template

---

## Critical Requirements

1. **The DOCX output must visually match the reference template exactly.** Open `reference_template.docx` and inspect every style, font, spacing before coding.

2. **Use the images from `templates/images/`** — do not recreate or substitute them.

3. **The product table prices must include the margin.** The margin is applied on top of the base `unit_cost_sar` from pricing items. Formula: `final_price = unit_cost_sar * (1 + margin_percent / 100)`.

4. **VAT is always 15%** of the subtotal.

5. **Payment terms are stored as free text** (`payment_terms_text`). The frontend Default mode validates that percentages sum to 100 before generating the text, but the backend only stores and renders the final text string.

6. **One quotation per project.** Regenerating replaces the previous one (delete old MinIO file, update DB row).

7. **Follow existing module patterns** — look at `pricing/` module for router dependencies, auth guards, tenant isolation patterns.

8. **Follow existing migration patterns** — use raw SQL for RLS policies, follow the 028 numbering convention.

9. **Follow existing MinIO patterns** — use `upload_file()`, `get_file_url()`, `delete_file()` from `app.shared.storage`.

10. **The document must handle long product tables gracefully** — tables spanning multiple pages should have the header/footer on each page and the table should not break mid-row.
