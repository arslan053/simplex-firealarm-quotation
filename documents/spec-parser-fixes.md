# Spec Parser & Extraction Fixes

This document describes two bugs in the spec extraction and structuring pipeline, their root causes, and the fixes applied. Use this to replicate the same fixes in a similar project.

---

## Bug 1: Wrapped List Items Split Into Separate Blocks

### Problem

When GPT returns a long list item that wraps across multiple lines in the Markdown output, the parser splits it into a `list_item` block (first line) and a separate `paragraph` block (continuation lines).

**Example GPT output:**

```
A. Fire alarm control panel shall be addressable type with minimum 2 loops
expandable to 4 loops and shall comply with latest edition of
NFPA 72 and UL 864.
```

**What the parser produced (wrong):**

| Block | Style | Content |
|-------|-------|---------|
| 1 | `list_item` | `A. Fire alarm control panel shall be addressable type with minimum 2 loops` |
| 2 | `paragraph` | `expandable to 4 loops and shall comply with latest edition of NFPA 72 and UL 864.` |

**What it should produce (correct):**

| Block | Style | Content |
|-------|-------|---------|
| 1 | `list_item` | `A. Fire alarm control panel shall be addressable type with minimum 2 loops\nexpandable to 4 loops and shall comply with latest edition of\nNFPA 72 and UL 864.` |

### Root Cause

The parser processed lines one at a time. When it detected a list item marker (`A.`, `1.`, `-`, etc.), it immediately emitted the block and moved on with `continue`. The next line had no marker, so it fell through to the paragraph accumulator. There was **no list item accumulation logic** — unlike paragraphs which accumulated consecutive lines, list items were single-line only.

### Key Insight

In Markdown, `\n` (single newline) is a soft wrap within the same block. `\n\n` (blank line) is a block separator. GPT uses single `\n` for wrapped lines within the same list item and `\n\n` between separate items.

### Fix

**File:** `parser.py` (the spec markdown parser)

Add list item accumulation that mirrors the existing paragraph accumulation:

1. Add `list_item_lines: list[str]` and `list_item_kind: str | None` accumulators
2. Add a `_flush_list_item()` function that joins accumulated lines and emits the block
3. When a list marker is detected: flush any previous list item, then start accumulating into `list_item_lines`
4. When a non-marker, non-blank line appears AND `list_item_lines` is non-empty: append it as a continuation line (don't fall through to paragraph)
5. Blank lines, headings, and new list markers all trigger `_flush_list_item()`

The logic flow becomes:
- Blank line → flush both list item and paragraph accumulators
- Heading → flush both, process heading
- List marker → flush previous list item, start new accumulation
- Plain text + inside list item → append as continuation
- Plain text + not inside list item → paragraph accumulation

---

## Bug 2: Sub-List Items Not Nested Under Parent List Items

### Problem

When a list item like `A. Section Includes:` has sub-items (`1.`, `2.`, `3.`), the parser treats them all at the same level with the same `parent_id` (the heading). There is no parent-child relationship between `A.` and its sub-items.

**Example PDF structure:**

```
A. Section Includes:
    1. Fire alarm control panel
    2. Smoke detectors
    3. Manual pull stations
B. Related Sections:
    1. Electrical
    2. Mechanical
```

**What the parser produced (wrong):**

| Content | Level | Parent |
|---------|-------|--------|
| `A. Section Includes:` | 3 | Heading |
| `1. Fire alarm control panel` | 3 | Heading |
| `2. Smoke detectors` | 3 | Heading |
| `B. Related Sections:` | 3 | Heading |

All items at the same level, all parented to the heading. No nesting.

**What it should produce (correct):**

| Content | Level | Parent |
|---------|-------|--------|
| `A. Section Includes:` | 3 | Heading |
| `1. Fire alarm control panel` | 4 | `A.` block |
| `2. Smoke detectors` | 4 | `A.` block |
| `B. Related Sections:` | 3 | Heading |
| `1. Electrical` | 4 | `B.` block |

### Root Cause

Two issues:

1. **GPT doesn't indent sub-items** — Without explicit instructions, GPT outputs all list items at the same indentation level (0 spaces). The parser has no signal to distinguish parent items from sub-items.

2. **Parser has no list nesting logic** — Even if GPT did indent, the parser strips all whitespace immediately (`line.strip()`) before processing, so indentation information is lost. There is no list item stack (unlike the heading stack that tracks heading hierarchy).

### Fix — Two Parts

**Part A: GPT Prompt Change**

**File:** `prompts.py` (the system prompt sent to GPT)

Add one rule to the spec-to-Markdown conversion section telling GPT to indent sub-list items:

> "When a list item contains sub-items (e.g., numbered items 1., 2. under a lettered item A.), indent each sub-item line by exactly 4 spaces to represent nesting. Apply this recursively for deeper levels (8 spaces for sub-sub-items, etc.)."

This makes GPT output:
```
A. Section Includes:
    1. Fire alarm control panel
    2. Smoke detectors
```

Instead of:
```
A. Section Includes:
1. Fire alarm control panel
2. Smoke detectors
```

**Part B: Parser Change**

**File:** `parser.py`

1. **Measure indentation before stripping:** `indent = len(line) - len(line.lstrip())` — do this before `stripped = line.strip()`
2. **Add a `list_stack`:** Similar to `heading_stack` but for list items: `list_stack: list[tuple[int, uuid.UUID]]` storing `(indent_level, block_id)`
3. **Track indent per list item:** Store `list_item_indent` when a new list marker is detected
4. **In `_flush_list_item()`:** Pop `list_stack` entries with indent >= current item's indent. If stack has entries remaining → this is a sub-item (parent = top of stack, level = heading_level + stack_depth + 1). If stack is empty → top-level item (parent = heading). After emitting, push onto `list_stack`.
5. **Clear `list_stack` on heading:** When a new heading is encountered, clear the list stack since list nesting resets.

### Important Design Decision

Do NOT add a new `sub_list_item` style/enum. A list item is a list item regardless of depth. The nesting is expressed through:
- `level`: incremented for deeper nesting (e.g., 3 for `A.`, 4 for `1.` under `A.`)
- `parent_id`: sub-item points to the parent list item's block ID, not the heading
- `list_kind`: stays `"bullet"` / `"numbered"` as-is

This requires no schema migration, no new enum values, and no frontend changes (the frontend already renders indentation based on `level * 16px`).

---

## Bug 3: Page Reload Loses BOQ/Spec State

### Problem

After uploading and extracting BOQ, if the user navigates away and comes back (or logs out and in), the project page shows "Upload a BOQ document first" even though BOQ data exists.

### Root Cause

The state flags `hasBoq`, `hasSpec`, `hasBoqExtracted` in the project detail page all default to `false` and are only set to `true` via in-session callbacks (when the user uploads/extracts during that session). On page reload, they reset.

### Fix

**File:** Project detail page component

In the `useEffect` that loads the project on mount, add three parallel API checks:

1. `listDocuments(projectId)` — if any BOQ documents exist → `hasBoq = true`
2. `listItems(projectId, {page:1, limit:1})` — if total items > 0 → `hasBoqExtracted = true`
3. `checkExisting(projectId)` (spec check) — if spec exists → `hasSpec = true`

No backend changes needed — the APIs already exist.
