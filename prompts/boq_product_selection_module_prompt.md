# Module: BOQ → Product Selection (Combo / Single) Decision

You are working inside an existing monorepo that already contains: -
Projects - Structured Specs stored in DB (Markdown structured
sections) - BOQs extracted and stored in DB - Product Selections table
(with product_codes array and descriptions array) - Project protocol
already decided: **MX or IDNet** - OpenAI model **5.2** already
configured in the system

IMPORTANT: - First read and follow
`./prompts/workflow_orchestration.md` - Treat it as **mandatory
operating rules** for this session. - Follow existing repo architecture
patterns. - Do NOT modify unrelated modules. - Keep changes minimal and
consistent with repo conventions.

------------------------------------------------------------------------

# Goal

For each BOQ item determine:

**Which product selection is the best match**.

A product selection may be:

-   **single product**
-   **combo (multiple product codes)**

The system must decide this by analyzing:

1.  BOQ item description
2.  Project Specs
3.  Product selections table (codes + description variants)

------------------------------------------------------------------------

# Important Context

The system already knows:

-   If the project is **MX**
-   Or **IDNet**

Therefore:

Only send product selections for **that side**.

Example:

If project = MX: - Send only product selections where `side = MX`

If project = IDNet: - Send only product selections where `side = IDNet`

Never mix both.

------------------------------------------------------------------------

# Inputs to Send to OpenAI

For **each BOQ item** send:

## 1) BOQ Item

-   description
-   unit
-   quantity
-   any extracted structured fields

IMPORTANT: If BOQ description indicates **panel equipment**, skip it
completely for now.

Panels must **not be sent to the model**.

------------------------------------------------------------------------

## 2) Project Specs

Send structured specs content retrieved from DB.

Specs are stored as structured markdown sections.

Send the relevant sections to provide context.

------------------------------------------------------------------------

## 3) Product Selections

From table:

`product_selections`

Send the following fields:

-   id
-   product_codes
-   selection_kind (`single` or `combo`)
-   descriptions (array)

Explain to the model that:

-   **descriptions array contains synonyms**
-   each description represents alternative wording of the same product

Example:

    descriptions = [
     "Addressable multi detector",
     "Multi sensor detector",
     "Combined smoke and heat detector"
    ]

Meaning: All describe the same selectable product.

------------------------------------------------------------------------

# Decision Rules (Very Important)

The model must follow this priority:

## 1️⃣ FIRST: Check Combo Products

Look at combo selections first.

If BOQ item clearly describes a combination device matching a combo:

Return the combo.

## 2️⃣ SECOND: Check Single Products

If the device clearly matches a single product and not a combo:

Return the single product.

## 3️⃣ THIRD: If No Clear Match

If no product selection matches:

Return **empty selection**.

Products list may not be complete.

This is acceptable.

------------------------------------------------------------------------

# Sequential Processing

Processing must be **sequential**:

1 BOQ → 1 LLM call

Process like:

BOQ 1 → call model → show result\
BOQ 2 → call model → show result\
BOQ 3 → call model → show result

Continue sequentially.

------------------------------------------------------------------------

# Output Format (Strict JSON)

The model must return:

    {
     "selection_id": "uuid | null",
     "selection_kind": "combo | single | none"
    }

Rules:

-   `selection_id` = ID from product_selections table
-   `selection_kind`
    -   combo
    -   single
    -   none

No extra text.

------------------------------------------------------------------------

# UI Display Requirements

Below each BOQ item show:

BOQ Description

Selected Product: - selection_kind - product_selection_id

Product Description: - show **only the FIRST description** from
descriptions array

Product Codes: - list of product_codes

If no match:

Selected Product → **Empty**

------------------------------------------------------------------------

# Skip Rules

If BOQ item refers to:

-   fire alarm panel
-   control panel
-   panel cabinet
-   panel accessories

Skip the item.

Do not send to model.

------------------------------------------------------------------------

# Deliverables

1)  Prompt file for model calls:

`./prompts/boq_product_selection_prompt.md`

2)  Service function:

Loads: - project specs - filtered product selections (MX or IDNet) - BOQ
items

Calls OpenAI sequentially.

3)  Result renderer:

Displays result under each BOQ item.

------------------------------------------------------------------------

# Run Verification

After implementation:

-   Run module
-   Process BOQ sequentially
-   Verify selections appear correctly
-   Verify skipped panel items are ignored
-   Verify empty matches handled safely
