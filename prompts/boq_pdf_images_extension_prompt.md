# Extend BOQ Module: PDF + Images Upload → OpenAI (GPT-5.2) → Excel → Existing BOQ Core Parser (NO CHANGES)


Also read the existing BOQ module prompt for reference and to avoid breaking existing behavior:
- `./prompts/boq_module_prompt.md` (existing Excel BOQ upload pipeline + MinIO + documents table + boq_items parsing + UI) 
- Other then reading from boq try to understand the pipeline from exiting code, explore it

IMPORTANT: The existing BOQ Excel pipeline is working and MUST NOT be changed. 
Your job is to add **two new ingestion paths** (PDF and Images) that both end by producing an `.xlsx` file and then passing that `.xlsx` into the **existing** BOQ Excel pipeline unchanged.

Keep changes minimal. Follow existing repo patterns (multi-tenancy, documents table usage, MinIO usage, workers/queues, UI patterns, error handling, logging). Do not redesign architecture.

---

## Current State (Do Not Change)

- BOQ Excel upload works: stores raw file in MinIO, creates documents record, parses Excel, applies rules, stores BOQ items.
- Required fields and validation rules exist in core Excel parser (description, quantity, unit, invalid rows, etc.).
- Multi-tenancy + RLS expectations already exist; follow same approach for any new table you add (if you add any).

---

## New Requirements

### A) Frontend: 3 BOQ Inputs (Left-to-right Buttons)

On the Project page, under BOQ:
1) **Upload Excel** (already working, keep as-is)
2) **Upload PDF** (at one time onw is allowed)
3) **Upload Images** (multiple images allowed)

UI behavior:
- The three controls should be visually separated and clear.
- While ANY BOQ parsing is running (Excel/PDF/Images), disable all BOQ upload buttons/controls until processing completes or is cancelled.
- After processing completes, user may upload another BOQ (multiple BOQs allowed over time; do not block future uploads).

---

### B) Images Flow (Multiple Images → One PDF → OpenAI → Excel)

1) User selects multiple images (jpg/png/webp etc).
2) Backend:
   - Temporarily store uploaded images in a temp directory (or temp bucket/path) during processing.
   - Convert ALL uploaded images into a single PDF (in the correct order selected).
   - Upload the generated PDF to MinIO (as the stored artifact for this BOQ import).
   - Create a documents row for the generated PDF using the existing documents system (same style as Excel does).
   - Ensure temporary images are deleted after:
     - PDF is generated AND uploaded to MinIO AND after response of open ai extraction succeeds/fails (always cleanup).
3) Extraction:
   - Send ALL images (not the generated PDF) to **OpenAI GPT-5.2** with strict instructions to extract ONLY the BOQ table into an Excel file.
4) Output:
   - OpenAI must return an `.xlsx` file ONLY (no extra text).
   - Do NOT store the returned `.xlsx` file in DB.
   - Pass the returned `.xlsx` bytes/file into the existing BOQ Excel parser pipeline unchanged, so it imports into `boq_items` as usual.
   - if store .xlsx temoprarily to preocess then delete it after output.

---

### C) PDF Flow (PDF Upload → OpenAI → Excel → Existing BOQ Core Parser)

1) User uploads a BOQ PDF.
2) Backend:
   - Store uploaded PDF in MinIO.
   - Create a documents row (type=BOQ) same as existing pipeline.
3) Extraction:
   - Send the PDF to **OpenAI GPT-5.2** with the same extraction rules as Images.
4) Output:
   - OpenAI returns `.xlsx` ONLY.
   - Do NOT store this `.xlsx` in DB.
   - Feed `.xlsx` into existing BOQ Excel parser pipeline unchanged.

---

## OpenAI Extraction Rules (GPT-5.2 ONLY)

Model: `gpt-5.2` (no other model).

The goal: extract ONLY the BOQ table and return ONLY an Excel file.

Core rules:
- Ignore non-BOQ paragraphs and any other text blocks that are not part of the BOQ table.
- Extract BOQ table rows top-to-bottom.
- Do not hallucinate: do not add rows, do not fill missing cells, do not “interpret” missing values.
- If a column (e.g., Description) is not present in the table, do NOT add it.
- Standardize column names ONLY for these 3 when clearly close matches:
  - Description
  - Quantity
  - Unit
  If a column name is not clearly close, keep it as-is (do not rename).
- Important multi-image behavior:
  - One image will contain the table header; other images may not.
  - Use the header image to learn column order/names and apply that same schema to subsequent images.

Numbering:
- Generate row numbers top-to-bottom based on extraction order; do not rely on original printed row numbers.
- Do not use image count or Excel row count as the source of truth; use the visual table order.

Output requirement:
- Return ONLY the Excel file (no markdown, no JSON, no explanation text).

---

## Prompt to Use (System + User)

Use strict prompts. You may keep them in a dedicated prompt file if that matches repo patterns.

SYSTEM_PROMPT (example):
"You are a BOQ table extraction engine.
You must return ONLY an .xlsx file.
Do not output any text.
Do not hallucinate or infer missing data.
Extract ONLY the BOQ table; ignore all paragraphs, notes, headers/footers, and non-table text.
If a value is missing or unreadable, leave the cell blank.
Do not add new columns that are not present.
Only standardize column headers for: Description, Quantity, Unit — and only when clearly close matches.
If not clearly close, keep the original header exactly.
For multi-image input: use the image that contains the header row as the schema for all images.
Extract rows in top-to-bottom order."

USER_MESSAGE (example):
"Extract the BOQ table and return ONLY an .xlsx file.
Inputs may be a PDF or multiple images.
Ignore all non-table content.
Do not add or guess missing values.
if dont find any boq table return empty .xlsx file
Keep other columns unchanged.
Standardize only Description/Quantity/Unit when clearly close.
Return ONLY the .xlsx file."

---

## Backend Integration Requirements (Minimal + Clean)

- Keep the existing BOQ Excel parsing module unchanged.
- Add a small adapter layer:
  - `boqPdfToExcel()` and `boqImagesToExcel()` that returns `.xlsx` bytes.
  - Then call the existing Excel ingestion function with that `.xlsx`.
- Use the existing documents table + MinIO patterns (same as Excel upload).
- Add progress status and cancellation for these new flows consistent with existing UI pattern.
- Ensure processing states disable all BOQ buttons until done.

---

## File / Module Separation

- Keep BOQ feature logic inside the BOQ module area, consistent with existing structure.
- make proper sepration of files as of openai (propmt plus other setup) and done put max code in few files like if we need to add file for bodq pdf handeling and images handeling then use seprate files for them. use even more then this professional pattren
- If using workers/queues, keep worker orchestration outside `modules/` and call BOQ services through a clean boundary (same philosophy as prior modules. but i think we dont need worker here if then dont use them.).

---

## Acceptance Criteria

- Project page shows 3 BOQ inputs: Excel (existing), PDF, Images.
- Images flow:
  - multiple images → combined PDF stored in MinIO → OpenAI GPT-5.2 extracts → returns `.xlsx` only → existing Excel BOQ pipeline imports → UI shows parsed results as before.
  - temp images cleaned up after completion/cancel/error.
- PDF flow:
  - PDF stored in MinIO → OpenAI extracts → returns `.xlsx` only → existing Excel BOQ pipeline imports → UI shows parsed results as before.
- During processing: all BOQ upload controls disabled; after completion: re-enabled.
- Multiple BOQs can be added sequentially (no “only one BOQ” restriction).
- No changes to existing BOQ Excel parsing logic, validations, or storage logic.

Start now and implement with minimal diffs.
