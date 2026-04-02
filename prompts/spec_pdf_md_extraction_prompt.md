# Implement Module: Specification PDF → Markdown Extraction (OpenAI GPT-5.2)

You are working inside an existing monorepo already containing:
- Authentication
- Multi-tenancy
- Admin dashboard
- Projects creation
- BOQ upload + parsing (already implemented)
- A common `documents` table/entity already used for BOQ (reuse it for Specification too)

All previous build prompts exist in `./prompts/`. You MUST read them first and follow the established patterns strictly. Do NOT redesign architecture.

---

## Goal (This Module Only)

Add Specification PDF upload and page-chunk extraction using **OpenAI GPT-5.2** to produce **ONLY Markdown**, ignoring:
- images/pictures/figures/logos
- Arabic text
- headers & footers (repeating page elements)
- tables entirely (do not reproduce table content)

Output must preserve the PDF’s visible structure:
- headings/subheadings
- numbered lists
- bullet lists
- paragraph breaks
Use `#`, `##`, `###` etc.

**Important:** For this prompt/task, results are NOT stored in DB. Show results on UI as they arrive.

---

## Core Flow

### 1) Upload
- Each Project can have:
  - 1 BOQ (already handled)
  - **ONLY 1 Specification file**
- When user uploads a specification PDF:
  - Upload file to MinIO (reuse existing MinIO logic from BOQ upload if present).
  - Create/update a `documents` record (reuse same table used by BOQ).
  - If a specification already exists for the project:
    - Show a warning: “A specification already exists. Uploading a new file will delete the previous one and start processing the new file.”
    - On confirm/upload: delete the old file from MinIO and remove old doc records (follow the repo’s existing pattern; keep minimal).
    - Start processing new one.

### 2) Chunking
- After upload, system checks page count.
- If pages > 10: split into chunks of 10 pages:
  - Example 27 pages → chunks: 10, 10, 7
- Each chunk is processed independently by a worker (see worker section).
- The frontend must show incremental chunk/page results as they are completed.

### 3) GPT-5.2 Extraction
- Use **ONLY** OpenAI model: `gpt-5.2`
- Extraction returns **ONLY Markdown** (no commentary, no fences, no metadata).
- Ignore pictures, Arabic, headers/footers, tables.
- Preserve heading/list structure as in PDF.

### 4) Display Results (No DB Storage)
- Show extracted Markdown grouped by chunk/pages.
- For each processed page (or chunk result split per page), UI should render:
  - a collapsible panel with “Hide/Show” toggle
  - appended results should not reset the current page view
- Add pagination in UI to navigate extracted pages/chunks.
- When a new chunk/page result arrives:
  - append it
  - keep user on the same page they are currently viewing (do not jump them)

### 5) Progress + Cancel
- While processing:
  - show progress bar (e.g., pages processed / total pages)
  - show cancel button
- Cancel must stop further processing:
  - worker stops remaining jobs
  - UI shows status “Cancelled”
  - already completed results remain visible

---

## Worker / Architecture Requirements (Very Important)

1) Use a worker system (architect-level):
   - 1 or more workers may handle chunk processing concurrently depending on configuration/need.
   - Keep it clean and minimal;

2) Frontend must be able to know when worker output is ready:
   Choose one method that matches repo patterns:
   - WebSocket / SSE stream progress + partial results
   - OR polling an API endpoint returning job status + results so far
   Implement the simplest approach consistent with existing codebase.

3) Separation of concerns:
   - Specification business logic must live inside the existing `specification` / `specs` module area (whatever naming pattern repo uses).
   - Worker implementation must NOT live inside `modules/` folder.
   - Workers should be in a separate top-level structure consistent with repo style.
   - Worker calls into the specs module via a clear boundary (service function), not mixing UI/db/api concerns.

---

## Handling “Chunk Context Loss” (GPT doesn’t know prior chunk)

We MUST reduce heading/subheading confusion across chunks, because chunk 2 has no context of chunk 1.

Implement ONE of these strategies (pick best minimal approach):

### Strategy A (Recommended Minimal):
Maintain a lightweight “Structure Context” string derived from the previous chunk’s output and pass it into the next chunk request:
- After chunk N finishes, derive:
  - last seen heading hierarchy (e.g. `# Part 1`, `## 1.1 Summary`, `### A. General`)
- Store this context IN MEMORY for the running job (not DB).
- When sending chunk N+1, prepend to the USER message it is for only for subsequent chunks not first one:
  - “Context: The document is currently under headings: … Continue preserving structure from this context if it continues.”

### Strategy B:
if you think strategy one wil not work efficiently and you have better solution then try that one. test it on one or two page pdf.

Pick Strategy A unless patterns suggest otherwise.

---

## OpenAI Setup (Key Handling)

- Create a dedicated OpenAI client setup file in the correct backend location following repo conventions.
- The OpenAI API key is stored in `./GitHubtoken2.txt`.
- On dev start (or setup script), read it and place it into `.env` (follow repo pattern; do not invent new secret flows).
- Never log the key.

---

## Prompting (Must Output ONLY Markdown)

Use a strict System Prompt like:

SYSTEM_PROMPT:
"You are a document conversion engine.

Return ONLY Markdown.

Do NOT add explanations.

Do NOT infer missing text.

Do NOT translate.

Ignore Arabic text completely.

Ignore all images/pictures/figures/logos.

Ignore tables entirely (do not reproduce table content).

Ignore headers and footers (repeating page elements).

Preserve the structure of headings/subheadings and bullet/numbered lists exactly as the PDF shows.

If something is unclear, omit it rather than guessing."

USER_MESSAGE template:
"Convert this PDF chunk into structured Markdown.

Use `#`, `##`, `###`, etc for headings.

Use numbered lists where numbered in PDF, bullets where bullets in PDF.

Do not include tables.

Do not include Arabic.

No extra text.



{OPTIONAL_CONTEXT_FROM_PREVIOUS_CHUNK}
"

IMPORTANT:
- The model response must be returned as-is to frontend (no reformatting).
- Enforce server-side validation: if model returns non-markdown commentary (e.g. “Here is the markdown:”), strip that entire prefix or reject and retry once with stronger instruction.

---

## UI Requirements

- Add Specification upload section under project.
- Reuse existing uploader/components from BOQ if possible.
- After upload, show:
  - progress bar
  - cancel button
  - live results area
- Results area:
  - items appended as pages complete
  - each page is collapsible (Hide/Show)
  - pagination to browse pages/chunks
  - preserve current page selection when new results arrive

---

## Backend Requirements

Provide endpoints consistent with existing API style.

Implement minimal endpoints needed for UI behavior.

---

## Deliverables

1) Code changes implementing:
   - spec upload
   - minio storage
   - doc record creation/replace
   - chunking logic
   - worker processing via GPT-5.2
   - progress + cancel
   - streaming/polling to UI
   - UI components + pagination + collapsible results

2) Provide a short README section (or update existing docs) explaining:
   - how to run workers
   - where to set OpenAI key
   - how the chunk context strategy works

---

## Constraints

- Do NOT redesign architecture.
- Follow patterns in `./prompts/` and existing code.
- Keep changes minimal and localized.
- Reuse existing components and services wherever possible.
- Do not store extraction results in DB for now.

Now implement this module.
