# Enhancement: Pipeline Orchestration — Run & Forget

First read and follow `./prompts/workflow_orchestration.md` as mandatory operating rules.

Read these files for full system context:
- `./prompts/backend_architect.md`
- `./prompts/frontend_structure_prompt.md`
- `./prompts/project_module_prompt.md`

---

## Overview

Convert the current multi-step manual workflow (user clicks 5+ buttons, waits between each) into a **single-click automated pipeline**. After the user uploads files, sets preferences, and fills quotation details — they click **one "Run" button** and the system chains all steps automatically until the final quotation is ready for download.

**No functionality changes.** Every step runs exactly as it does now. The only change is: instead of the user triggering each step manually, the backend orchestrator calls them in sequence automatically.

---

## Current Flow (Before)

```
Create Project → Upload BOQ/Spec → Click "Extract BOQ" → Wait →
Click "Analyze Spec" → Wait → Click "Match Devices" → Wait →
Click "Select Panels" → Wait → Click "Calculate Pricing" → Wait →
Open Quotation Modal → Fill details → Click "Generate" → Download
```

## New Flow (After)

```
Create Project → Upload BOQ/Spec + Set Optional Overrides + Fill Quotation Modal
→ Click "Run" → System runs everything automatically → Download
```

---

## Page Flow

### Page 1: Create Project (minimal changes)

Same as now: project_name, client_id, country, city, due_date. No changes to this page.

After creation, navigate to Page 2.

### Page 2: Project Setup (Upload + Overrides + Quotation Details)

This page has three sections:

**Section 1: Document Upload**
- BOQ upload (required) — same component and functionality as current ProjectDocuments
- Spec upload (optional) — same component and functionality as current ProjectDocuments
- Reuse existing upload components entirely

**Section 2: Optional Overrides**
- Clear heading explaining: "The system will automatically detect these from your BOQ and specifications. Only set these if you deliberately want to override the system's detection."
- Three optional dropdowns:
  - **Protocol**: Auto-detect (default) / MX / IDNET
  - **Notification Type**: Auto-detect (default) / Addressable / Non-addressable
  - **Network Type**: Auto-detect (default) / Wired / Fiber / IP
- Each dropdown shows a brief description of what it controls
- "Auto-detect" means the system decides — this is the default and recommended option

**Section 3: Quotation Details**
- A button labeled "Configure Quotation Details" that opens the **exact same QuotationModal** component already in use (both Step 1 and Step 2 of the modal)
- Reuse QuotationModal entirely — no new modal, no new fields, same validation
- After the modal is completed, show a summary card: "Quotation configured: Supply + Installation, 25% margin, Client: ABC Corp"
- The button changes to "Edit Quotation Details" after first completion

**Run Button:**
- At the bottom of the page
- **Disabled until**: BOQ is uploaded AND quotation details are filled (both steps of modal completed)
- Backend also validates these conditions before starting pipeline
- Label: "Run Full Analysis" with a play icon
- Confirmation dialog: "This will analyze your project and generate a quotation. This process takes 2-5 minutes. You can close this page and come back — the analysis will continue in the background. Continue?"

### Page 3: Pipeline Progress

After clicking Run, navigate to this page. Shows real-time progress:

```
┌─────────────────────────────────────────────────┐
│  Project Analysis in Progress                    │
│                                                  │
│  ✅ BOQ Extraction .................. Complete   │
│  ✅ Specification Analysis .......... Complete   │
│  🔄 Device Selection ............... Running     │
│  ⬜ Panel Configuration ............ Pending     │
│  ⬜ Pricing Calculation ............ Pending     │
│  ⬜ Quotation Generation ........... Pending     │
│                                                  │
│  ┌─────────────────────────────────────────┐    │
│  │  💡 Tip: You can close this page and    │    │
│  │  come back anytime. Your analysis will  │    │
│  │  continue running in the background.    │    │
│  └─────────────────────────────────────────┘    │
│                                                  │
│  Estimated time remaining: ~2 minutes            │
└─────────────────────────────────────────────────┘
```

**Progress features:**
- Each step shows: pending (gray), running (blue spinner), completed (green checkmark), failed (red X with error message)
- Poll backend every 3-5 seconds for status updates
- Show rotating tips/messages while user waits:
  - "You can close this page and come back — your analysis continues in the background."
  - "The system is analyzing your BOQ items and matching them to products."
  - "Almost there! Generating your quotation document."
  - (Rotate every 10-15 seconds)
- If user navigates away and comes back (or closes tab and reopens project), this page shows current progress — the pipeline runs on the backend regardless of browser state
- On completion: automatically transition to Page 4 (or show a "View Results" button)
- On failure: show which step failed, the error message, and a "Retry" button that resumes from the failed step

### Page 4: Final Results (New Clean Page)

A clean page with ONLY these elements — nothing else:

**Header:** Project name + status badge ("Completed")

**Action Buttons (prominent, top of page):**
1. **Download** — downloads the quotation DOCX file (same functionality as now)
2. **View** — opens quotation in new browser tab (same functionality as now)
3. **Edit** — opens the same two QuotationModal steps (pre-filled with the data the user entered initially). User can change any values. After saving:
   - Show "Save & Regenerate" button
   - Clicking it regenerates ONLY the quotation (not the full pipeline)
   - Old quotation is deleted from DB and MinIO
   - New quotation is stored
   - Page refreshes with new quotation
4. **View Details** — expands/toggles a section below showing two tables:
   - **Device Selection Table** — reuse the exact same DeviceSelectionSection component (same design, same columns, same values, same expand/collapse behavior)
   - **Panel Configuration Table** — reuse the exact same PanelConfigurationSection component (same design, same columns, same values, same expand/collapse behavior)
   - These are READ-ONLY on this page — no edit controls, no override toggles

**Project Documents Section (below actions):**
- Show uploaded BOQ and Spec documents
- Reuse same ProjectDocuments component
- **Upload/delete is DISABLED** — documents are locked after pipeline runs. Show them as read-only.

---

## Backend Architecture

### Pipeline Orchestrator

Create a new service that chains all steps:

```
backend/app/modules/pipeline/
├── __init__.py
├── router.py              -- Start pipeline, get status, retry
├── service.py             -- Orchestrator: chains steps in sequence
├── schemas.py             -- Pipeline status response schemas
└── models.py              -- PipelineRun model (tracks progress)
```

### Pipeline Status Model

New table `pipeline_runs`:

```sql
CREATE TABLE pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    project_id UUID NOT NULL REFERENCES projects(id),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
        -- pending | running | completed | failed
    current_step VARCHAR(30),
        -- boq_extraction | spec_analysis | device_selection |
        -- panel_selection | pricing | quotation_generation
    steps_completed JSONB NOT NULL DEFAULT '[]',
        -- ["boq_extraction", "spec_analysis", ...]
    error_message TEXT,
    error_step VARCHAR(30),
    retry_count INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_pipeline_runs_project ON pipeline_runs (tenant_id, project_id);

-- RLS policies (same pattern as other tables)
ALTER TABLE pipeline_runs ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_policy ON pipeline_runs
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
CREATE POLICY app_bypass_policy ON pipeline_runs
    USING (current_setting('app.tenant_id', true) IS NULL);
```

### Pipeline Orchestrator Service

```python
class PipelineService:
    STEPS = [
        "boq_extraction",
        "spec_analysis",
        "device_selection",
        "panel_selection",
        "pricing",
        "quotation_generation",
    ]

    async def run(self, tenant_id, project_id):
        """
        Execute all steps in sequence.
        Each step calls the EXACT same service method as the current manual trigger.
        No functionality changes — just automated sequencing.
        """
        for step in self.STEPS:
            update_status(current_step=step, status="running")
            try:
                await self._execute_step(step, tenant_id, project_id)
                append_to_steps_completed(step)
            except Exception:
                if retry_count < 1:
                    # Auto-retry once
                    retry_count += 1
                    try:
                        await self._execute_step(step, tenant_id, project_id)
                        append_to_steps_completed(step)
                    except Exception as e:
                        mark_failed(step, str(e))
                        return
                else:
                    mark_failed(step, str(e))
                    return
        mark_completed()
```

**Each step calls the existing service directly:**
- `boq_extraction` → `BoqExtractionService.run(tenant_id, project_id)`
- `spec_analysis` → `SpecAnalysisService.run(tenant_id, project_id)`
- `device_selection` → `DeviceSelectionService.run(tenant_id, project_id)`
- `panel_selection` → `PanelSelectionService.run(tenant_id, project_id)`
- `pricing` → `PricingService.calculate(tenant_id, project_id)`
- `quotation_generation` → `QuotationService.generate(tenant_id, project_id, quotation_inputs)`

**No changes to any existing service logic.** The pipeline just calls them in order.

### Pipeline Runs in Background

The pipeline must continue running even if the user closes the browser tab.

Use the same pattern as existing background jobs (e.g., `spec_analysis/router.py` uses `asyncio.create_task` with `get_worker_db`):

```python
@router.post("/run")
async def start_pipeline(project_id, request, user, db):
    # Create pipeline_run record
    # Launch background task
    asyncio.create_task(_run_pipeline_background(pipeline_run_id, tenant_id, project_id))
    return {"pipeline_run_id": ..., "status": "started"}
```

The background task uses `get_worker_db(tenant_id)` for its own DB session, independent of the request lifecycle.

### API Endpoints

```
POST /api/projects/{project_id}/pipeline/run
  - Validates: BOQ uploaded, quotation details saved
  - Creates pipeline_run record
  - Launches background task
  - Returns: { pipeline_run_id, status: "started" }
  - Requires: admin or employee role

GET /api/projects/{project_id}/pipeline/status
  - Returns current pipeline status:
    { status, current_step, steps_completed, error_message, error_step }
  - Frontend polls this every 3-5 seconds

POST /api/projects/{project_id}/pipeline/retry
  - Resumes pipeline from the failed step
  - Only works if status = "failed"
  - Resets error, continues from error_step
```

### Storing Quotation Inputs on Project

The quotation details (client_name, client_address, service_option, margin, payment_terms, inclusion_answers) need to be saved BEFORE the pipeline runs, so the quotation generation step can use them.

**Option A:** Add a JSONB column `quotation_inputs` on the `projects` table.
**Option B:** Create a new `project_quotation_config` table.

Use whichever fits the existing codebase patterns better. The data stored:

```json
{
  "client_name": "ABC Corp",
  "client_address": "Riyadh, KSA",
  "subject": "Fire Alarm System",
  "service_option": 2,
  "margin_percent": 25.0,
  "payment_terms_text": "25% advance, 70% delivery, 5% completion",
  "inclusion_answers": {"key1": true, "key2": false}
}
```

**Endpoint to save quotation inputs (before pipeline runs):**
```
POST /api/projects/{project_id}/quotation-config
  - Saves quotation inputs to project
  - Same validation as current QuotationModal
  - Returns saved config
```

### Storing Optional Overrides

The optional overrides (protocol, notification_type, network_type) are stored on the existing project model fields:
- `project.protocol` — if user sets MX/IDNET, save here before pipeline runs
- `project.notification_type` — if user sets addressable/non_addressable, save here
- `project.network_type` — if user sets wired/fiber/IP, save here

These fields already exist on the Project model. Just save the user's choice before the pipeline starts.

**Endpoint to save overrides (or include in an existing endpoint):**
```
PATCH /api/projects/{project_id}/overrides
  - Body: { protocol?: string, notification_type?: string, network_type?: string }
  - Only saves non-null values
  - Returns updated project
```

### How Overrides Affect the Pipeline

**CRITICAL: No existing service logic changes except these specific behaviors:**

**Protocol override (affects spec_analysis):**
- Spec analysis runs fully as normal — parses spec, answers questions, saves spec blocks, saves analysis answers to DB
- At the end, when it calls `_derive_protocol()` and tries to set `project.protocol`:
  - **Check:** if `project.protocol` was already set by user (before pipeline started) → do NOT override it
  - The `protocol_auto` field still gets the system's detected value (for reference)
  - Only `project.protocol` is protected from override when user set it explicitly

**Notification type override (affects device_selection):**
- Device selection runs as normal
- **If user set notification_type explicitly:** add a dynamic instruction to the GPT prompt:
  - "IMPORTANT: The user has explicitly requested {addressable/non_addressable} notification devices. You MUST only provide {addressable/non_addressable} notification devices. Do not use {the other type}."
- The `notification_type_auto` field still gets the system's detected value
- Only `project.notification_type` is protected from override when user set it explicitly

**Network type override (affects device_selection):**
- Network type does NOT affect device selection matching logic
- If user set network_type explicitly, save it to `project.network_type` before pipeline
- Device selection may still set `network_type_auto` with its own detection
- If user already set `project.network_type`, do NOT override it — same pattern as protocol

### Locking Documents After Pipeline Starts

Once the pipeline starts:
- BOQ and Spec documents cannot be re-uploaded or deleted
- Add a check: if `pipeline_runs` exists for this project with status in ("running", "completed"), reject upload/delete requests with 409: "Documents are locked after analysis has started."
- Frontend disables upload/delete controls when pipeline has been run

### Quotation Regeneration (Edit Flow)

When user clicks Edit on the final page and changes quotation details:

```
POST /api/projects/{project_id}/quotation/regenerate
  - Accepts same inputs as current generate endpoint (GenerateQuotationRequest)
  - Deletes old quotation record from DB
  - Deletes old quotation file from MinIO
  - Generates new quotation with updated inputs
  - Stores new quotation record
  - Returns new QuotationResponse
```

This does NOT re-run the pipeline. Only quotation generation runs again with the new inputs.

---

## Frontend Architecture

### New/Modified Files

```
frontend/src/features/projects/
├── pages/
│   ├── ProjectSetupPage.tsx        -- NEW: Upload + Overrides + Quotation Config + Run
│   ├── PipelineProgressPage.tsx    -- NEW: Step-by-step progress display
│   ├── ProjectCompletedPage.tsx    -- NEW: Final results (Download/View/Edit/Details)
│   ├── CreateProjectPage.tsx       -- UNCHANGED
│   └── PricingPage.tsx             -- REMOVE (no longer a separate page)
├── components/
│   ├── QuotationModal.tsx          -- UNCHANGED (reused on setup page and completed page)
│   ├── DeviceSelectionSection.tsx  -- UNCHANGED (reused read-only on completed page)
│   ├── PanelConfigurationSection.tsx -- UNCHANGED (reused read-only on completed page)
│   ├── ProjectDocuments.tsx        -- MINOR CHANGE: add read-only mode prop
│   └── PipelineProgress.tsx        -- NEW: progress display component with tips
├── api/
│   └── pipeline.api.ts            -- NEW: pipeline start, status, retry endpoints
└── types/
    └── pipeline.ts                -- NEW: PipelineStatus interface
```

### Routing Changes

```tsx
// REMOVE these routes:
// { path: 'projects/:projectId/results', element: <ProjectResultsPage /> }
// { path: 'projects/:projectId/device-selection', element: <DeviceSelectionPage /> }
// { path: 'projects/:projectId/pricing', element: <PricingPage /> }

// ADD these routes:
{ path: 'projects/:projectId/setup', element: <ProjectSetupPage /> },
{ path: 'projects/:projectId/progress', element: <PipelineProgressPage /> },
{ path: 'projects/:projectId/completed', element: <ProjectCompletedPage /> },
```

After project creation, navigate to `/projects/:projectId/setup`.

When user opens a project:
- If pipeline never started → go to `/setup`
- If pipeline running → go to `/progress`
- If pipeline completed → go to `/completed`
- If pipeline failed → go to `/progress` (shows error + retry)

### ProjectSetupPage

**Section 1: Documents**
- Reuse `ProjectDocuments` component for BOQ and Spec upload
- Same exact UI and functionality

**Section 2: Optional Overrides**
- Card with heading: "Analysis Preferences (Optional)"
- Subtext: "Leave these on Auto-detect to let the system decide based on your documents. Only change them if you have a specific requirement."
- Three dropdowns (using existing `Input` or a `Select` component):
  - Protocol: Auto-detect / MX / IDNET
  - Notification Type: Auto-detect / Addressable / Non-addressable
  - Network Type: Auto-detect / Wired / Fiber / IP
- Each with a one-line description

**Section 3: Quotation Configuration**
- A button: "Configure Quotation Details"
- Opens the **exact same QuotationModal** — both steps (project details + inclusions)
- After completion, show a summary card with the configured values
- Button changes to "Edit Quotation Details"

**Run Button:**
- Fixed at bottom or prominent position
- Disabled until: BOQ uploaded + Quotation modal completed
- Tooltip on disabled state: "Upload a BOQ file and configure quotation details to start"
- On click: confirmation dialog → start pipeline → navigate to progress page

### PipelineProgressPage

- Polls `GET /api/projects/{project_id}/pipeline/status` every 3-5 seconds
- Shows each step with status icon (pending/running/completed/failed)
- **Rotating tips** while waiting (change every 10-15 seconds):
  - "You can close this page and come back anytime. Your analysis continues in the background."
  - "The system is extracting items from your Bill of Quantities..."
  - "Analyzing specifications and determining system protocol..."
  - "Matching BOQ items to the best products..."
  - "Configuring panel products and accessories..."
  - "Calculating pricing for all selected products..."
  - "Generating your final quotation document..."
  - (Show contextual tips based on current_step when possible)
- On completion: show success message + "View Results" button → navigates to completed page
- On failure: show which step failed, error message, "Retry" button
- **Persistence:** If user navigates away and comes back, this page resumes showing progress from backend state. No frontend state dependency.

### ProjectCompletedPage

Clean page with only these elements:

**1. Header**
- Project name
- "Completed" badge (green)
- Completion date

**2. Action Buttons (Card or button group)**
- **Download** — same as current download functionality
- **View** — opens in new browser tab, same as current preview functionality
- **Edit** — opens the same QuotationModal (both steps), pre-filled with the data user entered initially. After editing:
  - Changes are saved
  - "Save & Regenerate Quotation" button appears
  - Clicking it calls the regenerate endpoint
  - Old quotation is deleted (DB + MinIO), new one is created
  - Page refreshes with new quotation, opens in new tab automatically
- **View Details** — expands a collapsible section below with:
  - **Device Selection Table** — reuse `DeviceSelectionSection` component in read-only mode (no override toggles, no edit controls). Same columns, same values, same design.
  - **Panel Configuration Table** — reuse `PanelConfigurationSection` component in read-only mode. Same columns, same values, same design.

**3. Project Documents (below actions)**
- Reuse `ProjectDocuments` component in **read-only mode**
- Shows uploaded BOQ and Spec files
- Upload/delete buttons hidden or disabled
- User can still view/download the uploaded documents

---

## Important Implementation Rules

1. **NO functionality changes to existing services.** BOQ extraction, spec analysis, device selection, panel selection, pricing, quotation generation — all run exactly as they do now. The pipeline just calls them in sequence.

2. **Reuse existing components.** QuotationModal, DeviceSelectionSection, PanelConfigurationSection, ProjectDocuments — use them as-is. Add a `readOnly` prop where needed to disable editing controls.

3. **No new UI design.** Use existing shared components (Card, Button, Input, Badge). Follow existing design patterns and Tailwind classes. The only new visual element is the progress page.

4. **Pipeline runs on backend.** Uses `asyncio.create_task` + `get_worker_db` pattern (same as existing spec_analysis background jobs). Browser state is irrelevant — pipeline continues regardless.

5. **Auto-retry once on failure.** If a step fails, retry it once automatically. If it fails again, mark as failed and show error to user with manual retry option.

6. **Remove old step-by-step pages.** The separate DeviceSelectionPage, PricingPage, and the manual trigger buttons on ProjectResultsPage are replaced by the pipeline. Old completed projects should still show their data on the new completed page (the data is already in DB — the completed page just reads it).

7. **Inclusion questions** are handled by the system at quotation generation time — same as now. The QuotationModal Step 2 collects them. No changes to how inclusions work.

---

## Migration & Database Changes

1. **New table:** `pipeline_runs` (as defined above)
2. **New column on projects:** `quotation_config JSONB` — stores quotation inputs before pipeline runs
3. **New column on projects:** `pipeline_status VARCHAR(20)` — quick-access status without querying pipeline_runs (optional, for faster list queries)

---

## Deliverables

1. **Alembic migration** — `pipeline_runs` table + project columns
2. **Backend pipeline module** — `backend/app/modules/pipeline/` with orchestrator, router, schemas, model
3. **Quotation config endpoint** — save/retrieve quotation inputs on project
4. **Overrides endpoint** — save optional overrides on project
5. **Pipeline status polling endpoint** — for frontend progress display
6. **Retry endpoint** — resume from failed step
7. **Quotation regenerate endpoint** — regenerate only (not full pipeline)
8. **Document locking** — prevent upload/delete after pipeline starts
9. **Override handling** — protect user-set protocol/notification_type/network_type from system override
10. **Frontend: ProjectSetupPage** — upload + overrides + quotation modal + run button
11. **Frontend: PipelineProgressPage** — step-by-step progress with tips and polling
12. **Frontend: ProjectCompletedPage** — download/view/edit/details with reused components
13. **Frontend: routing changes** — new routes, remove old routes
14. **Frontend: pipeline API** — start, status, retry calls
15. **Remove old pages** — PricingPage (separate), old manual trigger buttons

---

## Constraints

- Do NOT change any existing service logic (boq_extraction, spec_analysis, device_selection, panel_selection, pricing, quotation)
- Do NOT create new UI components where existing ones can be reused
- Do NOT invent new designs — follow existing patterns
- Do NOT modify how inclusions work — they are handled by the system at quotation generation time
- Do NOT add email notifications — in-app progress only
- Follow existing module patterns for backend structure
- Follow existing patterns for frontend feature structure
- All database tables must have RLS policies
