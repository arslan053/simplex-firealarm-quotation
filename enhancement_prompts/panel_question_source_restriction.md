# Enhancement: Panel Selection LLM — Source Restriction Rule (BOQ vs Spec)

## Problem Statement

The panel selection LLM prompt previously told the model to "analyze ALL BOQ items and the specification text" and answer "Yes if the BOQ or specification clearly mentions the feature" — for **every** question, regardless of what the question actually says.

But each question explicitly names its source:

| Questions | Text says... | Should search |
|---|---|---|
| Q2, Q3, Q14, Q17, Q18, Q20 | "Does the **BOQ** require/mention..." | BOQ only |
| Q21, Q206 | "...from the **BOQ**..." | BOQ only |
| Q201, Q202, Q203 | "Do the **specifications** call for..." | Spec only |
| Q204 | "Does the **BOQ or specification** require..." | Both |

Without enforcing this, the LLM would answer "Yes" to Q14 ("Does the **BOQ** mention a printer?") even if only the spec mentions it — and vice versa for spec-only questions. This produces wrong answers because the downstream code trusts the LLM's answer as reflecting that specific source.

---

## Implementation

**File:** `backend/app/modules/panel_selection/service.py`

### Update `SYSTEM_PROMPT`

Replace the generic "analyze ALL BOQ items and the specification text" instruction with an explicit **Source Restriction Rule** at the top of the Instructions section.

The rule has 4 cases:

1. **Question mentions "BOQ" only** → Search ONLY BOQ items. Even if the specification explicitly mentions the feature, answer "No" if the BOQ does not. The specification is irrelevant for these questions.

2. **Question mentions "specification"/"specifications" only** → Search ONLY the specification text. Even if the BOQ explicitly lists the feature, answer "No" if the specification does not mention it. The BOQ is irrelevant for these questions.

3. **Question mentions both "BOQ" and "specification"** → Search BOTH sources. Answer "Yes" if either source mentions the feature.

4. **Question does not mention a specific source** → Search BOTH sources. Answer "Yes" if either source mentions the feature.

The `inferred_from` field must match where the evidence was actually found: "BOQ", "Spec", "Both", or "Neither".

### No-spec fallback

When no specification is available ("No specification document available" or empty):
- BOQ-only and both-source questions: rely on BOQ items
- Spec-only questions: answer "No" since no spec is available, set `inferred_from` to "Neither"

---

## Current Question Sources (for reference)

These are the questions loaded from `prompt_questions` table across three categories:

### `4007_panel_questions` — All BOQ-only
- **Q2**: "Does the **BOQ** require speakers, amplifiers, or audio notification devices?"
- **Q3**: "Does the **BOQ** require telephone jacks, FFT, or fire warden intercom?"
- **Q14**: "Does the **BOQ** mention a printer or require printing capability?"
- **Q17**: "Does the **BOQ** mention a repeater panel, remote annunciator, or LCD annunciator?"
- **Q18**: "Does the **BOQ** mention a graphic annunciator, mimic panel, or mimic display?"
- **Q20**: "Does the **BOQ** mention a panel-mounted annunciator, built-in annunciator, or door-mounted annunciator?"

### `4100ES_panel_questions` — Mix of spec-only and both
- **Q201**: "Do the **specifications** call for a touchscreen display, multi-line display, or bilingual/2-language support?" → **Spec only**
- **Q202**: "Do the **specifications** call for backup or redundant amplifiers?" → **Spec only**
- **Q203**: "Do the **specifications** call for Class A wiring for speakers or telephone circuits?" → **Spec only**
- **Q204**: "Does the **BOQ or specification** require BMS integration or BACnet connectivity?" → **Both**
- **Q206**: "What is the total telephone jack count from the **BOQ**?" → **BOQ only**

### `multi_panel_questions` — BOQ-only
- **Q21**: "For each **BOQ item** that describes a fire alarm control panel, extract the number of SLC loops..." → **BOQ only**

---

## Files Modified

| File | Change |
|---|---|
| `backend/app/modules/panel_selection/service.py` | `SYSTEM_PROMPT` — replaced generic "analyze all" instruction with explicit 4-case Source Restriction Rule |

No migrations, no seeds, no frontend changes. Single file, prompt-only edit.

---

## Why This Matters

- **Q201 (touchscreen)**: Only specs can require touchscreen — a BOQ listing "touchscreen panel" as a line item doesn't mean the spec requires it. Without this rule, BOQ items could falsely trigger touchscreen selection.
- **Q14 (printer)**: Only BOQ should drive printer detection — if the spec mentions "printer connectivity" as a general capability but no printer is in the BOQ, the answer should be "No".
- **Q204 (BMS)**: Correctly searches both — BMS can appear in either BOQ or spec.
- This ensures each downstream code path gets answers from the source it trusts.
