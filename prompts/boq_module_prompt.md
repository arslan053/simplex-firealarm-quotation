```text
Claude Code: Implement BOQ Handling Module (Phase 0 – Step 3)

Read these file ./project_module_prompt.md first (It will give you the basic idea of previous module project module):

You can see foloowing file  as well if need the whole context of the project 

- ./project-scope-techstack.md
- ./backend_architect.md
- ./frontend_structure_prompt.md
- ./multitenant_prompt.md
- ./project_module_prompt.md

You have already implemented multi-tenancy + auth foundation admin dashboard and the Project module.

Now implement the BOQ Handling module only, exactly as described below.

Do NOT implement Specs module, OCR, pricing logic, rules engine, or quotation export yet.

====================================
BOQ HANDLING MODULE – FUNCTIONAL REQUIREMENTS
====================================

1) Where this module lives (Project-first flow)

- The system is multi-tenant with roles (Super Admin / Admin / Employee).
- A Project is created by an Employee/Admin.
- User starts from the Projects list.
- When user selects a project, the app opens a dedicated Project page/route representing that single project.
- On the Project page, user sees project-level options/modules including:
  - Import BOQ (Excel)
  - (Specs later, not included now)

2) BOQ Upload (Frontend → Backend)

On the Project page:
- User selects an Excel file (.xlsx).
- Frontend sends upload request to backend (multipart/form-data).
- While backend is processing, UI shows a loading state (spinner/progress indicator) according to the project’s existing UI pattern.
- When processing completes, the user sees a clear status message:
  - “Document parsed successfully.” (success)
  - Or “Parsing failed: <field> is missing.” (failure)

If any of the 3 required fields cannot be extracted (Description / Quantity / Unit), show which one is missing (or list multiple missing fields).

Backend:
- Stores the raw uploaded file in MinIO.
- Creates a Document record in DB (to reference this uploaded file).
- Parses the uploaded Excel file to extract BOQ rows.

Add:
- Setup MinIO fully if needed. If anything is required from me (credentials/keys/endpoints/buckets), ask me. Do not invent random MinIO values.

3) Parsing Rules (Excel → extracted columns)

Goal: extract and store these fields per BOQ line:
- rowNumber (mandatory; can be called Row Number / Order)
- description
- quantity
- unit

Header variations supported:
- Description may appear as:
  - Description
  - Item Description
  - Part Description
  - Parts Description
- Quantity may appear as:
  - Qty
  - Quantity
- Unit may appear as:
  - Unit
  - UOM
- The parser must handle different names of columns by normalizing header text:
  - convert to lowercase
  - trim spaces
  - compare against known variants

Row handling (core rules):
- Skip empty rows.
- Quantity is parsed into a numeric value where possible.
- Unit is stored as text.
- Each extracted row becomes one DB record, linked to the project.

Add:
- If a line is missing required values at row-level:
  - If description is missing, mark the BOQ row as invalid (do not skip).
  - If quantity is missing or non-parsable, mark invalid.
  - If unit is missing, mark invalid.
- After parsing completes, show status indicating that some BOQ items are invalid (if any), while still importing valid rows.

4) Storage Model (What gets saved and how it links)

A) Documents table (one row per uploaded file)

Purpose: keep a DB record for each uploaded file so you can:
- link it to a project
- know who uploaded it
- know the original name / size
- store the MinIO object reference (so the file can be fetched later)
- connect parsed BOQ items back to the exact uploaded file

Table: documents
- id (PK)
- projectId (FK → projects.id)
- uploadedByUserId (FK → users.id)
- type (string/enum like BOQ now; later SPEC)
- originalFileName (string)
- fileSize (number)
- objectKey (string) → the MinIO object reference/key for this uploaded file
- createdAt
- updatedAt

B) BOQ items table (one row per extracted BOQ line)

Purpose: store extracted BOQ line items and keep traceability to:
- which project it belongs to
- which uploaded BOQ file it came from

Table: boq_items
- id (PK)
- projectId (FK → projects.id)
- documentId (FK → documents.id) ✅ points to the uploaded BOQ file record
- rowNumber (integer) ✅ mandatory (or name it order)
- description (text)
- quantity (decimal/float)
- unit (string)
- isHidden (boolean, default false)
- isValid (boolean, default true) ✅ indicates if the row has all required fields parsed correctly
- createdAt
- updatedAt

Abive multi-tenant tables must include the tenant identifier column using a single, consistent name across the entire application (e.g., tenant_id or company_id in every table such as projects, users, etc.).

Row-Level Security (RLS) must be enabled wherever tenant data exists; if any existing table is missing RLS, add tenant_id (same name) and apply RLS policies to enforce tenant isolation at the database level.

✅ Key decision: every BOQ line stores documentId so it always knows which uploaded BOQ file produced it.

5) After Import: View + Hide/Unhide

Once import is complete:
- If parsing failed, user sees the failure indication (example: “Parsing failed: Quantity field is missing.”).
- If parsing succeeded, user sees “Document parsed successfully.” and gets an option to Show BOQ Items.

Show BOQ Items:
- On “Show”, display a table (scrollable/expandable as suits your UI) with columns:
  - Row Number
  - Description
  - Quantity
  - Unit
  - Status (Valid/Invalid)
- On “Hide”, the table is hidden/collapsed again.

Additionally:
- User can hide/unhide individual BOQ items (isHidden) for later steps.

6) End-to-end flow summary (one pass)

- User opens a Project page.
- User uploads BOQ Excel.
- UI shows a spinner/progress indicator while processing.
- Backend stores file in MinIO.
- Backend creates documents row (type=BOQ).
- Backend parses Excel → extracts rowNumber/description/quantity/unit.
- If missing required columns → UI shows parsing failed with missing field(s).
- If success → UI shows “parsed successfully” + user can show/hide the BOQ table.
- Backend inserts rows into boq_items, each with:
  - projectId
  - documentId
  - isValid flag
- UI displays BOQ items table, including valid/invalid status and hide/unhide control.

====================================
BACKEND REQUIREMENTS
====================================

- Add schema/migration updates for:
  - documents table
  - boq_items table (including isValid)
- Add endpoints for:
  - Upload BOQ Excel (multipart/form-data) for a project
  - List BOQ items for a project (include hide/unhide + valid/invalid fields)
  - Update BOQ item hide/unhide (toggle isHidden)
- Enforce multi-tenancy and ownership rules already established:
  - Employee can operate only on their own project
  - Admin access follows project module rules
- Apply RLS policies where necessary (including tenant-owned tables introduced here).

====================================
FRONTEND REQUIREMENTS
====================================

- Add UI inside the Project Detail page:
  - Upload BOQ Excel control
  - Processing spinner/progress state
  - Success/failure status banner
  - Show/Hide BOQ Items table
- Table must support:
  - valid/invalid status display
  - hide/unhide per row
- Follow existing UI patterns and feature-first structure.

====================================
DELIVERABLE
====================================

1) MinIO setup integrated (ask me for required values if needed).
2) Backend migrations + endpoints implemented for documents + boq_items.
3) Frontend project page updated with BOQ import UI and BOQ items table.
4) End-to-end flow works locally:
   Project → Upload BOQ → Parse → Status → Show table → Hide/unhide items

Start now.
```

GENERAL COMMAND (use this when running the coding agent)

Read and follow this BOQ module prompt file, and confirm the codebase already has working auth, multi-tenancy by domain, admin dashboard, authorization/RBAC, and the Projects module implemented. Then implement ONLY this BOQ Handling Module (Phase 0 – Step 3) without adding other modules.
