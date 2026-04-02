# Enhancement: Workstation Networking Type Detection & Storage

## Context

The device selection pipeline uses an LLM to match BOQ items to product selectables. Among these selectables are **graphics workstations** (category `annunciator_subpanel`, subcategory `work_station`) — fire alarm monitoring PCs that come in different variants depending on the **networking type** (fiber / wired / IP) and whether **override** functionality is included.

Previously, the LLM prompt had a vague instruction to "check the spec for wired/copper or fiber" when matching workstations. There was no structured detection, no project-level storage of the networking type, and no enforcement that the workstation variant must match the project's networking type.

---

## What Was Implemented

### 1. Database: `network_type` column on `projects` table

**Migration:** `backend/alembic/versions/024_add_network_type_to_projects.py`

Added `network_type VARCHAR(10)` — nullable, no default. Allowed values: `"fiber"`, `"wired"`, `"IP"`, or `NULL`.

**Model:** `backend/app/modules/projects/models.py`

Added field:
```python
network_type: Mapped[str | None] = mapped_column(String(10), nullable=True, default=None)
```

Follows the same pattern as `protocol` (also `String(10)`, nullable).

### 2. LLM Prompt Updates in `backend/app/modules/device_selection/service.py`

Two rules in `SYSTEM_PROMPT` were updated/added:

#### Rule 14(a) — Workstation matching (updated)

The workstation variant MUST match the project's networking type resolved in rule 15. The LLM uses both `specification_hints` on the workstation selectables and the resolved `network_type` to pick the correct variant. Override vs no-override is also used to disambiguate.

#### Rule 15 — Networking type detection (new)

Core logic:

- **Networking is NOT always needed.** It is only required when EITHER:
  - (i) A workstation / graphics station exists in the BOQ items, OR
  - (ii) Multiple MAIN fire alarm panels exist in the BOQ (main panels = primary fire alarm control panels, NOT repeaters/annunciators/subpanels/mimic panels)
- If NEITHER condition is true → `network_type` = null (project does not need networking)
- When networking IS needed, determine type from BOQ + spec keywords:
  - "fiber", "fiber optic", "optical fiber" → `"fiber"`
  - "wired", "copper", "ethernet", "CAT5", "CAT6", "RJ45" → `"wired"`
  - "IP", "IP-based", "TCP/IP", "network IP" → `"IP"`
- Also check `specification_hints` on workstation selectables for networking clues
- **Defaults when networking IS needed:**
  - If no clear type found, or both "fiber" and "wired" mentioned → default to `"wired"`
  - If override not mentioned → default to no-override
- The workstation MUST have the same networking type as the project

#### Output format

Added `network_type` field to the LLM JSON response:
```json
{
  "notification_protocol": "<addressable or non_addressable or null>",
  "network_type": "<fiber or wired or IP or null>",
  "matches": [...]
}
```

### 3. Backend Service Logic in `run()` method

After all LLM batches complete:

- Extract `network_type` from the LLM response
- If valid (`"fiber"`, `"wired"`, `"IP"`) → store on project via `UPDATE projects SET network_type = :nt`
- If null or missing → set project's `network_type` to `NULL` (no networking needed)
- Logged at INFO level for traceability

### 4. Relationship Between Networking and Workstation

These are closely related but distinct concepts:

- **Networking type** = a project-level attribute (fiber/wired/IP/null) — determined by whether networking is needed and what type
- **Workstation** = a selectable product that requires networking — its variant is constrained by the networking type
- A workstation triggers networking detection, but so do multiple main panels
- The workstation variant MUST match the project's network type — this is enforced in the LLM prompt

---

## Files Modified

| File | Change |
|------|--------|
| `backend/alembic/versions/024_add_network_type_to_projects.py` | **Created** — migration adding `network_type` column |
| `backend/app/modules/projects/models.py` | **Modified** — added `network_type` field |
| `backend/app/modules/device_selection/service.py` | **Modified** — rule 14(a) updated, rule 15 added, output format updated, storage logic in `run()` |

---

## How to Re-apply This Enhancement

If you need to re-implement this from scratch (e.g., on a fresh codebase or after a rollback):

1. **Create migration** to add `network_type VARCHAR(10)` nullable column to `projects` table. Follow the pattern of migration 018 (which added `protocol`).

2. **Add `network_type` field** to the `Project` model in `backend/app/modules/projects/models.py` as `Mapped[str | None] = mapped_column(String(10), nullable=True, default=None)`.

3. **Update `SYSTEM_PROMPT`** in `backend/app/modules/device_selection/service.py`:
   - In rule 14(a): Replace the vague "check spec for wired/fiber" with explicit instruction that workstation variant MUST match the project's `network_type` from rule 15.
   - Add rule 15: Networking type detection with the two trigger conditions (workstation OR multiple main panels), keyword detection, defaults (wired + no-override), and null when not needed.

4. **Update output format** in the prompt to include `"network_type": "<fiber or wired or IP or null>"` before `matches`.

5. **Update `run()` method**:
   - Initialize `network_type: str | None = None` before the batch loop.
   - Extract `network_type` from parsed LLM response inside the batch loop.
   - After all batches: if valid value → UPDATE project; if null → SET network_type = NULL on project.

6. **Run migration**: `alembic upgrade head`

---

## Key Design Decisions

- **network_type is nullable** — null means "networking not needed", which is different from "wired" (the default when networking IS needed but type is unclear)
- **Stored as simple String(10)**, not a Postgres enum — matches the `protocol` column pattern, avoids migration complexity with async enums
- **LLM decides both networking need and type** — it scans all BOQ items to determine if workstation or multiple main panels exist, then detects type from keywords
- **"IP" stored uppercase** — "fiber" and "wired" are lowercase, "IP" is uppercase for readability
- **Override is a prompt-level concept only** — it affects workstation variant selection but is not stored as a separate project field (it's embedded in the workstation selectable choice)
