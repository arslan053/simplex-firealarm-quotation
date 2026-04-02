# Implement: Store Specification Markdown Output into DB (Block Tree) + UI Enhancements

Read and follow `./prompts/workflow_orchestration.md` first; treat it as mandatory operating rules for this session.
Then follow established patterns in this repo. Keep changes minimal. Do NOT redesign architecture.

You MUST also read and align with:
- `./prompts/spec_pdf_md_extraction_prompt.md`
and any other relevant prompts inside `./prompts/`.

---

## Context

We already implemented (or are implementing) Specification PDF extraction using OpenAI GPT-5.2 in chunks (10 pages per chunk). Currently results are shown but NOT stored.

Now we have an issue: we receive results as Markdown (with headings, paragraphs, list items). We must store these results into DB using the exact schema approach described below, and adjust UI to show structured chunk/page results with metadata and expand/collapse.

This task MUST:
- keep worker orchestration clean and separate from module logic (as per earlier architecture rules)
- keep spec-related parsing logic inside the specs module (professional separation)
- not mix with other similar projects; stay inside this repo only

---

## DB Storage Design (No Additions, Use Exactly This)

Create a new table for specification parsed blocks using EXACTLY these columns and meanings:

- `id` UUID PK
- `document_id` UUID NOT NULL
- `page_no` INT NOT NULL
- `parent_id` UUID NULL
- `order_in_page` INT NOT NULL  (stable order)
- `style` TEXT  (**Heading1 | Heading2 | Heading3 | Heading4 | Heading5 | Heading6 | paragraph | list_item**)
- `level` INT NULL  (**this is the DEPTH of the block in the tree; paragraphs can have depth too**)
- `list_kind` TEXT NULL  (bullet | numbered)
- `content` TEXT NOT NULL  ✅ store the exact original Markdown line as returned (including the marker such as `A.` / `1.` / `-`)

Rules (UPDATED — only these rules changed):
- Heading mapping is based on markdown hashes and MUST ALWAYS be treated as a heading:
  - If a line starts with `#` then it is ALWAYS a heading (never paragraph, never list item).
  - `#` => `style=Heading1`
  - `##` => `style=Heading2`
  - ...
  - `######` => `style=Heading6`
  - If more than 6 hashes exist, do NOT go above 6: treat as `style=Heading6` (cap at 6).
  - Example: `## 1.1 DESCRIPTION:` is a HEADING (Heading2), not a list item.
- Depth rule:
  - `level` stores the depth of the block in the logical tree.
  - Headings use their logical depth based on heading nesting.
  - Paragraphs may appear under any heading depth and must store the same depth as their parent heading context (e.g., if current heading context is depth 4, paragraph rows use `level=4`).
  - Each sibling/child relationship must be consistent so the tree can be reconstructed deterministically.
- Paragraphs:
  - each paragraph must be its own row/chunk
  - system must reliably detect paragraph boundaries (when a paragraph ends) and split accordingly
- List items:
  - store each list line as `style=list_item`
  - `list_kind=bullet` if the marker is `-` or `*`
  - `list_kind=numbered` if line starts with `1.` or `1)` or `A.` or `a.` or similar enumerators
  - IMPORTANT: `content` must include the enumerator/marker as part of the stored text (example: `A. The fire alarm...`)
- Fallback:
  - If a line cannot be confidently classified as heading or list item, store it as `style=paragraph`.

Indexing:
- Add indexes ONLY where necessary. Do not overuse.
- At minimum ensure efficient retrieval for:
  - document_id + page ordering
  - parent traversal
Use the smallest number of indexes needed.

---

## Parsing + Parent Assignment Requirements

Implement a deterministic parsing pipeline that converts the Markdown returned by OpenAI into rows of the above table.

Parent rules:
- Maintain current heading context with a stack while parsing lines.
- For a heading line:
  - parent_id should be the nearest previous heading of smaller level (if any), else NULL.
- For paragraph or list_item lines:
  - parent_id should be the most recent heading currently active (deepest heading in stack), else NULL.

Order:
- `order_in_page` must be stable and deterministic.
- It must preserve the exact order the content appears for that page.

Page association:
- Each stored row MUST have `page_no`.
- Because extraction is chunk-based, ensure the system can map lines to the correct page_no.
- Reuse the existing chunking/page split approach already used in the extraction flow. Do not invent a new PDF splitting mechanism unless required by existing patterns.

---

## Worker Behavior Change (Critical)

When chunk 2 (and later chunks) start processing, the worker system must NOT wait until the entire specification is done to store results.

Instead:
- As soon as a chunk result returns from OpenAI, the worker must immediately:
  1) parse the returned Markdown
  2) convert it into DB rows according to the schema above
  3) store them
  4) notify the frontend that:
     - page/chunk is complete
     - DB now contains structured rows for those pages

This must work for chunk 1, chunk 2, etc. Incrementally.

Cancel behavior:
- If user cancels during processing:
  - stop remaining chunk jobs
  - do not delete already stored rows for completed pages
  - UI shows cancelled state and keeps stored results visible

Replacement behavior:
- Only one specification file allowed:
  - if user uploads a new one, the old spec file is deleted and old parsed rows for that document/spec are deleted as part of replacement
  - then start processing/storing new file

---

## API Changes

Extend existing specification endpoints (reuse repo patterns) so the frontend can:
- fetch stored structured rows from DB (paged)
- receive progress updates and know when new pages are available
- request “raw chunk markdown” viewing if the UI needs “see more”

Do NOT return only the raw markdown anymore as the main data.
The main data is the stored DB rows.

However, UI must still be able to view the raw chunk markdown if it was trimmed:
- If raw output is trimmed, UI must show “See more” and allow the user to view the full raw chunk output
- Implement the minimal mechanism consistent with current design:
  - store the raw chunk output temporarily (in memory cache or minimal persistence) OR re-fetch by re-running the chunk if your existing architecture already supports that
  - pick the simplest approach consistent with repo patterns
Do NOT redesign storage broadly.

---

## UI Changes (Critical)

In the results area:
- Do NOT show the PDF pages as a single raw markdown blob.
- Show chunk/page results using the stored DB block rows.

Requirements:
1) Show per-chunk and/or per-page grouping with metadata:
   - page number must be visible
   - show style per row (Heading1..Heading6 / paragraph / list_item)
   - show level (depth) when relevant
2) Each page/chunk section must be collapsible (Hide/Show).
3) If the raw OpenAI output was trimmed for a chunk:
   - show “See more” and allow the user to view the full raw chunk output
4) Pagination:
   - implement pagination for browsing pages/rows
   - when new pages arrive, append to the dataset but keep the user on the same currently selected page (do not jump)
5) Reuse existing frontend components whenever possible.
6) Progress bar + cancel button must remain and reflect stored progress.

---

## Keep Parsing Engine Separate and Professional

When implementing the conversion logic, keep it separated cleanly:
- Worker orchestration stays outside `modules/`
- Spec parsing/conversion pipeline lives in the specs module area as a dedicated service (professional boundary)
- Keep parsing rules isolated in their own file(s) inside the specs module (do NOT scatter parsing logic across controllers/routes)

The worker should call a single specs service function like:
- `convertAndStoreSpecMarkdown(document_id, chunk_meta, markdown_text)`

Do not mix UI concerns inside the service.
Do not mix DB schema migrations inside random places; follow the repo migration pattern.

---

## Acceptance Criteria

- Upload spec PDF → chunks processed → results stored incrementally in DB.
- UI shows stored structured rows (with page_no + style + level + content).
- Hide/Show per page/chunk works.
- “See more” works when raw chunk output is trimmed.
- Cancel stops future chunks, preserves already stored pages.
- Re-upload replaces old spec and deletes old stored rows cleanly.
- Tenant isolation preserved; RLS applied where needed following repo pattern.
- Minimal indexes only; no over-indexing.
- No architecture redesign; reuse existing patterns.

Now implement this end-to-end: DB migration + backend store/retrieve + worker incremental conversion + UI updates.
