# 4100ES Panel Selection Logic
## For Review by Fire Alarm Engineer

This document describes the step-by-step logic for selecting a Simplex 4100ES panel
and all its required components. Each rule comes directly from our reference file.

A fire alarm engineer should read this and confirm: "Yes, this is correct" or flag errors.

---

## STEP 1: Entry Gate — When Do We Pick the 4100ES?

The 4100ES panel is selected when **ANY ONE** of these four conditions is true:

| # | Condition | Source |
|---|-----------|--------|
| 1 | Total detection devices (detectors + manual pull stations + monitor modules + control modules + line isolators) is **more than 1000** | Row 1 |
| 2 | The BOQ or Specs call for **speakers or amplifiers** | Row 2 |
| 3 | The BOQ or Specs call for **telephone jacks or firefighter telephone (FFT)** | Row 3 |
| 4 | The BOQ or Spec mentions a **loop count greater than 6** (e.g. "8-loop panel") | Q21 |

These are **OR conditions** — if any one is true, we select the 4100ES.

> **Important context:** In the 4007 and 4010 panels, conditions 2 and 3 cause a
> "Gate Fail" (those panels cannot support speakers/telephone). For 4100ES, these
> are *entry conditions* — the 4100ES is specifically designed to handle audio
> and telephone.

### Loop Count Decision Factor (Q21)

The LLM is asked (Q21) to extract the SLC loop count from the BOQ/spec. If the
BOQ doesn't mention any loop count, Q21 returns `"null"` and does not affect the
panel decision. If multiple loop counts are mentioned, the **largest** is used.

**Panel loop capacities:**
- **4007** supports up to **2 loops**
- **4010** (any bay) supports up to **6 loops**
- **4100ES** handles **more than 6 loops**

**How loop count affects panel selection (when 4100ES is NOT already triggered):**

| Loop Count | Effect |
|---|---|
| null (not mentioned) | No effect — decision based on other factors only |
| 1–2 | No effect — stays within 4007 range |
| 3–6 | If device count selected 4007, **upgrades to 4010** (loops exceed 4007 capacity) |
| 7+ | **Triggers 4100ES** (condition #4 above) |

---

## STEP 2: Master Controller (Default — Always Pick One)

Exactly **one** of these two master controllers is selected. Never both.

### Option A: Standard LCD Display — `4100-9701` (qty 1)
**What it is:** Master Controller with 2-line x 40-character LCD display.

**Select this when:**
- Specs do NOT call for a touchscreen display, AND
- Specs do NOT call for a multi-line display, AND/OR
- Specs call for an 80-character LCD display

### Option B: Touchscreen Display — `4100-9706` (qty 1)
**What it is:** Master Controller with color touchscreen display.

**Select this when:**
- Specs call for a touchscreen display, OR
- Specs call for a multi-line display, OR
- Specs call for bilingual / 2-language support

### Decision Rule
> If the spec mentions touchscreen, multi-line, bilingual, or 2-language → pick `4100-9706`.
> Otherwise → pick `4100-9701`.
> Pick exactly one, never both.

---

## STEP 3: Mandatory Default Items (Always Included)

These are **always** selected regardless of any conditions. Every 4100ES panel needs them.

| Product | What It Is | Qty | Why |
|---------|-----------|-----|-----|
| `4100-0646` | PDM Harness Cable | 1 | Connects the panel to the Power Distribution Module. Mandatory. |
| `4100-0635` | Power Distribution Module (PDM) | 1 | Provides power distribution inside the panel. Mandatory. |

> **Note:** Additional quantities of 4100-0646 and 4100-0635 may be needed later
> (see Steps 9 and 10). This is just the initial default qty 1 each.

---

## STEP 4: Detection Loop Cards (Based on Protocol)

The project's protocol (MX or IDNET) determines which loop card to use,
and the **number of detection devices** determines how many cards.

### If Protocol = MX → `4100-6311` (ESMX Loop Card)
**What it is:** An MX loop interface card that connects MX-protocol detection devices to the panel.

**Quantity rule:** Select **1 card for every 150 detection devices** (round up).

| Detection Devices | Cards Needed |
|-------------------|-------------|
| 1 – 150 | 1 |
| 151 – 300 | 2 |
| 301 – 450 | 3 |
| ... | ceil(devices / 150) |

### If Protocol = IDNET → `4100-3109` (IDNet 2 Module)
**What it is:** An IDNet loop interface card that connects IDNET-protocol detection devices to the panel.

**Quantity rule:** Select **1 card for every 200 detection devices** (round up).

| Detection Devices | Cards Needed |
|-------------------|-------------|
| 1 – 200 | 1 |
| 201 – 400 | 2 |
| 401 – 600 | 3 |
| ... | ceil(devices / 200) |

> **"Detection devices"** = the same count used in the 4007/4010 panel logic:
> sum of BOQ item quantities where the matched selectable category is
> `mx_detection_device` or `idnet_detection_device`.

---

## STEP 5: Notification Cards (Based on Notification Type)

The type of notification appliances in the project determines which card,
and the **number of horn/flasher/strobe devices** (excluding speakers) determines how many cards.

Speakers are **not** counted here — they are handled separately by amplifiers in Step 6.

### If conventional (non-addressable) horn/flashers → `4100-5450` (NAC Card)
**What it is:** A conventional Notification Appliance Circuit card. Drives non-addressable horns, strobes, and horn/strobes.

**Quantity rule:** Select **1 card for every 45 horn/flasher/strobe devices** (round up).

### If addressable horn/flashers → `4100-5451` (Addressable Notification SLC Module)
**What it is:** An addressable IDNAC module. Drives TrueAlert ES and TrueAlert addressable notification appliances.

**Quantity rule:** Select **1 card for every 45 horn/flasher/strobe devices** (round up).

| Horn/Flasher Devices | Cards Needed |
|---------------------|-------------|
| 1 – 45 | 1 |
| 46 – 90 | 2 |
| 91 – 135 | 3 |
| ... | ceil(devices / 45) |

> **"Horn/flasher devices" (`hornflasher_count`)** = sum of BOQ item quantities
> where the matched selectable has `subcategory` of: `horn`, `horn_flasher`,
> `flasher`, `strobe`, `strobe_flasher`, or `speaker_flasher`.
>
> **Why `speaker_flasher` is included:** A speaker/flasher combo device has two
> parts — the speaker part is counted toward amplifiers (Step 6), and the flasher
> part needs a NAC circuit (this step). So `speaker_flasher` contributes to both counts.

---

## STEP 6: Audio — Speakers & Amplifiers

This step only applies **if the BOQ or Specs call for speakers**.

> **"Speaker count" (`speaker_count`)** = sum of BOQ item quantities where the
> matched selectable has `subcategory` of: `speaker` or `speaker_flasher`.
>
> **Why `speaker_flasher` is included:** The speaker part of a speaker/flasher
> combo needs an amplifier channel. The flasher part is counted separately in Step 5.

### 6a. Basic Audio Module — `4100-1412` (qty 1)
**What it is:** ES Net Basic Audio module with microphone. Required once when speakers are in the project.

**When:** BOQ or Specs calls for speakers → always qty 1.

### 6b. Amplifier Selection (Pick ONE type, not both)

Look at the Specs to decide which amplifier type:

#### Option 1: Standard Amplifier — `4100-1333` (100W Digital Amplifier)
**What it is:** 100-watt amplifier with 6 NACs, 220VAC, 70V.

**Select when:** Specs do **NOT** call for backup/redundant amplifiers.

**Quantity rule:** Select **1 amplifier for every 100 speakers** (round up).

| Speakers | Amplifiers Needed |
|----------|------------------|
| 1 – 100 | 1 |
| 101 – 200 | 2 |
| 201 – 300 | 3 |
| ... | ceil(speakers / 100) |

#### Option 2: Backup Amplifier — `4100-1327` (50W Flex Amplifier)
**What it is:** 50-watt amplifier with 3 NACs, 70V. Has backup/redundancy capability.

**Select when:** Specs call for backup/redundant amplifiers.

**Quantity rule:** Select **1 amplifier for every 50 speakers** (round up).

| Speakers | Amplifiers Needed |
|----------|------------------|
| 1 – 50 | 1 |
| 51 – 100 | 2 |
| 101 – 150 | 3 |
| ... | ceil(speakers / 50) |

---

## STEP 7: Telephone / FFT

This step only applies **if the BOQ or Specs call for firefighter telephone or telephone jacks**.

### 7a. Master Telephone — `4100-1270` (qty 1)
**What it is:** Master Telephone module with 3 NACs. Required once when telephone/FFT is in the project.

**When:** BOQ or Specs calls for telephone jacks or FFT → always qty 1.

### 7b. Expansion Phone Controller — `4100-1272`
**What it is:** Additional telephone jack controller card.

**When:** BOQ calls for telephone jacks.

**Quantity rule:** Select **1 card for every 45 telephone jacks** (round up).

| Telephone Jacks | Cards Needed |
|-----------------|-------------|
| 1 – 45 | 1 |
| 46 – 90 | 2 |
| ... | ceil(jacks / 45) |

---

## STEP 8: Class A Wiring Adapters (Conditional on Specs)

These are only needed **if the project specifications call for Class A wiring**.

### 8a. For Speakers with Standard Amplifier (4100-1333)
**Product:** `4100-1249` (100W Class A Adapter)

**When:** Class A wiring is needed AND amplifier is `4100-1333`.

**Quantity:** Same quantity as `4100-1333` (1 adapter per amplifier).

### 8b. For Speakers with Backup Amplifier (4100-1327)
**Product:** `4100-1246` (Flex 50 Class A Adapter)

**When:** Class A wiring is needed AND amplifier is `4100-1327`.

**Quantity:** Same quantity as `4100-1327` (1 adapter per amplifier).

### 8c. For Telephone Jacks
**Product:** `4100-1273` (Phone Class A NAC Adapter)

**When:** Class A wiring is needed AND telephone jacks exist.

**Quantity:** Same quantity as `4100-1272` (1 adapter per phone controller).

---

## STEP 9: Printer & BMS Integration (Simple Fixed Qty)

### 9a. Printer — `4100-6038` (qty 1)
**What it is:** Dual RS-232 interface card for printer connection.

**When:** BOQ or Specs calls for a printer **AND** there is NO workstation in the project.

If the project has a workstation (a BOQ item matched to a selectable with
`subcategory = 'work_station'`), the printer card is **NOT** selected — the
workstation handles printing on its own.

| Printer in BOQ/Spec? | Workstation in project? | Select `4100-6038`? |
|---|---|---|
| Yes | No | **Yes** — panel needs its own printer card |
| Yes | Yes | **No** — workstation handles printing |
| No | Either | **No** — printer not required |

### 9b. BMS Integration — `4100-6069` (qty 1) + serial interface fallback
**What it is:** BACnet Ethernet module for Building Management System integration.

**When:** BOQ or Specs calls for BMS integration (Q204 = Yes).

BMS also requires the serial interface card (`4100-6038`). If the printer card was already
selected in Step 9a, the interface is already present. If the printer card was **not** selected
(either no printer needed or workstation handles printing), the system adds `4100-6038`
automatically as a BMS interface fallback.

| BMS needed? | Printer card selected (9a)? | Products added |
|---|---|---|
| Yes | Yes | `4100-6069` only — interface already there from printer |
| Yes | No | `4100-6069` + `4100-6038` (BMS interface fallback) |
| No | — | Nothing |

---

## STEP 10: 8-Switch/8-LED Module & LED Controller

These modules provide physical switch and LED indicators on the panel front.

### 10a. 8-Switch and 8-LED Module — `4100-1461`
**What it is:** A panel-front module with 8 switches and 8 LEDs for zone/device control.

**Quantity rule (add up all that apply):**

| Condition | Qty of 4100-1461 to add |
|-----------|------------------------|
| For every `4100-1333` (standard amplifier) | 1 per amplifier |
| For every 2 pcs of `4100-1327` (backup amplifier) | 1 per 2 amplifiers (round up) |
| For every 2 pcs of `4100-1272` (phone controller) | 1 per 2 controllers (round up) |

**Example:** If you have 3x `4100-1333` and 4x `4100-1272`:
- From amplifiers: 3
- From phone controllers: 4/2 = 2
- **Total 4100-1461 = 5** 
**Note** simply if aove items are not there then it will not be selected. its purely depend upon the qty of 4100-1333, 4100-1327 and 4100-1272

### 10b. LED Controller — `4100-1450`
**What it is:** Controls the LED modules. One is needed for every 4 LED/switch modules.

**Quantity rule:** Select **1 for every 4 pcs of `4100-1461`** (round up).

| 4100-1461 Qty | 4100-1450 Needed |
|---------------|-----------------|
| 1 – 4 | 1 |
| 5 – 8 | 2 |
| 9 – 12 | 3 |
| ... | ceil(qty_1461 / 4) |

**Note** simply if 4100-1461 is not selected in above operation then it will not be selected. its purely depend upon the qty of 4100-1461. so make sure when the decission is made it store and the enxt question have this state.
---

## STEP 11: Networking (From Project Network Type)

This step uses the **`project.network_type`** value that was determined and stored during
device selection. Unlike 4007/4010 (which use LLM questions Q15/Q16/Q19 to decide
networking), the 4100ES reads the project's already-resolved networking type directly.

**When networking is needed:** `project.network_type` is set to `"wired"`, `"fiber"`, or `"IP"`
when EITHER a workstation exists in the BOQ OR multiple main panels are present.

**When networking is NOT needed:** `project.network_type` is `NULL` — skip this entire step.

### Option A: Wired (Copper) Networking — `project.network_type = "wired"`

| Product | Qty |
|---------|-----|
| `4100-6078` (Network Interface Card) | 1 |
| `4100-6056` (Network Media Card — Wired) | 2 |

### Option B: Fiber Optic Networking — `project.network_type = "fiber"`

| Product | Qty |
|---------|-----|
| `4100-6078` (Network Interface Card) | 1 |
| `4100-6301` (SM-L Duplex Fiber Media) | 1 |
| `4100-6302` (SM-R Duplex Fiber Media) | 1 |

### Option C: IP Networking — `project.network_type = "IP"`

| Product | Qty |
|---------|-----|
| `4100-2504` (CS Gateway with IP) | 1 |

> **Source of truth:** `project.network_type` is determined during device selection by
> examining the BOQ and spec for networking keywords (fiber/wired/IP). It defaults to
> `"wired"` when networking is needed but the type is unclear. The workstation selected
> during device selection must match this same networking type.
>
> **Why not LLM questions?** The 4007/4010 panels still use Q15/Q16/Q19 (LLM Yes/No
> questions) for their networking child cards. The 4100ES does NOT use those questions —
> it uses the project-level `network_type` instead, ensuring consistency between the
> workstation variant and the panel networking cards.

---

## STEP 12: Power Supply Cards — `4100-5401`

**What it is:** Additional power supply card. The panel needs extra power supplies based on the total card load.

**This is the most complex calculation.** Count from ALL of the following rules and add them up:

| Rule | Condition | Qty of 4100-5401 |
|------|-----------|-------------------|
| Rule 1 | For each group of 6 cards combining: `4100-3109` (IDNET loop) + `4100-1272` (phone controller) + `4100-5450` (conventional NAC) | 1 per 6 cards |
| Rule 2 | For every 2 pcs of `4100-1327` (backup amplifier) | 1 per 2 amplifiers |
| Rule 3 | For each group combining: `4100-3109` qty 4 + `4100-1272` + `4100-5451` qty 1 | 1 per such combination |
| Rule 4 | For each `4100-5451` (addressable NAC) | 1 per card |
| Rule 5 | For every 2 pcs of `4100-1333` (standard amplifier) | 1 per 2 amplifiers |
| Rule 6 | For every 3 pcs of `4100-6311` (MX loop card) | 1 per 3 cards |

### How to apply these rules:

**If Protocol = MX:**
- Count MX loop cards (`4100-6311`) from Step 4 → apply **Rule 6**: `ceil(qty_6311 / 3)`
- Count conventional NAC cards (`4100-5450`) from Step 5 → these go into **Rule 1** pool
- Count addressable NAC cards (`4100-5451`) from Step 5 → apply **Rule 4**: 1 per card
- Count amplifiers → apply **Rule 2** or **Rule 5** depending on type

**If Protocol = IDNET:**
- Count IDNET loop cards (`4100-3109`) from Step 4
- Count phone controllers (`4100-1272`) from Step 7
- Count NAC cards (`4100-5450` or `4100-5451`) from Step 5
- Pool the IDNET loops + phone controllers + conventional NACs for **Rule 1**: `ceil(total / 6)`
- Addressable NACs go to **Rule 4**: 1 per card
- Count amplifiers → apply **Rule 2** or **Rule 5** depending on type

**Total `4100-5401` = sum of all applicable rules.**

---

## STEP 13: Additional Power Cables — `4100-0646`

**Recall:** Step 3 already added 1x `4100-0646` as default.

**Additional quantity:** For every `4100-5401` power supply from Step 12, add 1x `4100-0646`.

**Total `4100-0646` = 1 (default) + qty of `4100-5401` from Step 12.**

---

## STEP 14: Additional PDMs — `4100-0635`

**Recall:** Step 3 already added 1x `4100-0635` as default.

**Additional quantity needed for:**

| Condition | Extra 4100-0635 |
|-----------|----------------|
| For every 3 pcs of `4100-5401` (power supply) | 1 |
| For every 3 pcs of `4100-1333` (standard amplifier) | 1 |

**Total `4100-0635` = 1 (default) + ceil(qty_5401 / 3) + ceil(qty_1333 / 3).**

---

## STEP 15: Expansion Bays — `4100-2300`

**What it is:** An expansion bay adds physical space inside the enclosure for additional cards.

**Quantity — add up all that apply:**

| Condition | Qty of 4100-2300 |
|-----------|-----------------|
| For every `4100-5401` (power supply) | 1 per power supply |
| For every `4100-1333` (standard amplifier) | 1 per amplifier |

**Total `4100-2300` = qty_5401 + qty_1333.**

---

## STEP 16: Filler Plates — `4100-1279`

**What it is:** Blank filler plates to cover unused slots in expansion bays.

**Quantity:** 8 pcs for every `4100-2300` expansion bay.

**Total `4100-1279` = qty_2300 x 8.**

---

## STEP 17: Enclosure Selection (Greedy Bin-Packing)

Select the optimal combination of enclosures to house all power supplies and standard
amplifiers. Each enclosure has a fixed capacity:

| Enclosure | Code | Capacity (slots) |
|-----------|------|-------------------|
| 3-Bay | `2975-9443` | 3 |
| 2-Bay | `2975-9442` | 2 |
| 1-Bay | `2975-9441` | 1 |

### Input
```
total_slots = qty_PSU (4100-5401) + qty_standard_amp (4100-1333)
```

### Algorithm: Greedy Denomination

Use the largest enclosure first, then fill the remainder with the smallest that fits.
This minimizes total enclosure count while avoiding wasted capacity.

```
qty_3bay  = total_slots // 3
remainder = total_slots % 3

if remainder == 2 → add 1× 2-bay
if remainder == 1 → add 1× 1-bay
if remainder == 0 → nothing extra

Special case: total_slots == 0 → 1× 1-bay (minimum one enclosure required)
```

### Examples

| Total Slots (PSU + Amp) | 3-bay (`2975-9443`) | 2-bay (`2975-9442`) | 1-bay (`2975-9441`) | Total Enclosures |
|---|---|---|---|---|
| 0 | — | — | 1 | 1 |
| 1 | — | — | 1 | 1 |
| 2 | — | 1 | — | 1 |
| 3 | 1 | — | — | 1 |
| 5 | 1 | 1 | — | 2 |
| 7 | 2 | — | 1 | 3 |
| 9 | 3 | — | — | 3 |
| 10 | 3 | — | 1 | 4 |
| 14 | 4 | 1 | — | 5 |

> Multiple enclosures may be selected. The algorithm always produces the minimum
> number of enclosures with no wasted capacity.

---

## COMPLETE PRODUCT SUMMARY TABLE

| Step | Product Code | What It Is | Qty Logic |
|------|-------------|-----------|-----------|
| 2 | `4100-9701` OR `4100-9706` | Master Controller | 1 (pick one based on spec) |
| 3 | `4100-0646` | PDM Harness Cable | 1 default + 1 per power supply |
| 3 | `4100-0635` | Power Distribution Module | 1 default + extras per Step 14 |
| 4 | `4100-6311` | MX Loop Card | ceil(detection_devices / 150) — MX only |
| 4 | `4100-3109` | IDNET Loop Module | ceil(detection_devices / 200) — IDNET only |
| 5 | `4100-5450` | Conventional NAC Card | ceil(hornflasher_count / 45) — conventional only |
| 5 | `4100-5451` | Addressable NAC Module | ceil(hornflasher_count / 45) — addressable only |
| 6a | `4100-1412` | Basic Audio Module | 1 (if speakers) |
| 6b | `4100-1333` | Standard Amplifier (100W) | ceil(speakers / 100) — no backup spec |
| 6b | `4100-1327` | Backup Amplifier (50W) | ceil(speakers / 50) — backup spec |
| 7a | `4100-1270` | Master Telephone | 1 (if telephone/FFT) |
| 7b | `4100-1272` | Phone Controller | ceil(phone_jacks / 45) |
| 8a | `4100-1249` | Class A Adapter (100W) | = qty of 4100-1333 (if Class A spec) |
| 8b | `4100-1246` | Class A Adapter (50W) | = qty of 4100-1327 (if Class A spec) |
| 8c | `4100-1273` | Phone Class A Adapter | = qty of 4100-1272 (if Class A spec) |
| 9a | `4100-6038` | Printer Interface | 1 (if printer AND no workstation) |
| 9b | `4100-6069` | BMS Integration | 1 (if BMS) |
| 9b | `4100-6038` | BMS Interface Fallback | 1 (if BMS AND printer card not selected) |
| 10a | `4100-1461` | 8-Switch/8-LED Module | see Step 10 formula |
| 10b | `4100-1450` | LED Controller | ceil(qty_1461 / 4) |
| 11 | `4100-6078` | Network Interface Card | 1 (if `project.network_type` = wired or fiber) |
| 11 | `4100-6056` | Wired Network Media | 2 (if `project.network_type` = wired) |
| 11 | `4100-6301` | Fiber Media Left | 1 (if `project.network_type` = fiber) |
| 11 | `4100-6302` | Fiber Media Right | 1 (if `project.network_type` = fiber) |
| 11 | `4100-2504` | IP Gateway | 1 (if `project.network_type` = IP) |
| 12 | `4100-5401` | Power Supply Card | see Step 12 formula |
| 13 | `4100-0646` | PDM Harness (extra) | = qty of 4100-5401 |
| 14 | `4100-0635` | PDM (extra) | ceil(qty_5401 / 3) + ceil(qty_1333 / 3) |
| 15 | `4100-2300` | Expansion Bay | = qty_5401 + qty_1333 |
| 16 | `4100-1279` | Filler Plates | = qty_2300 x 8 |
| 17 | `2975-9443` / `2975-9442` / `2975-9441` | Enclosure(s) | Greedy bin-packing: total_slots // 3 × 3-bay, remainder → 2-bay or 1-bay |

---

## EXAMPLE WALKTHROUGH

**Scenario:** 1200 detection devices, MX protocol, addressable notification (90 devices),
BOQ calls for speakers (150 speakers, no backup spec), no telephone, no Class A,
specs say touchscreen display, `project.network_type` = wired, no printer, no BMS.

| Step | Decision | Product | Qty |
|------|----------|---------|-----|
| 1 | 1200 > 1000 → 4100ES | — | — |
| 2 | Touchscreen spec | `4100-9706` | 1 |
| 3 | Default | `4100-0646` | 1 |
| 3 | Default | `4100-0635` | 1 |
| 4 | MX, 1200 devices, ceil(1200/150) = 8 | `4100-6311` | 8 |
| 5 | Addressable, 90 horn/flasher devices, ceil(90/45) = 2 | `4100-5451` | 2 |
| 6a | Speakers exist | `4100-1412` | 1 |
| 6b | No backup, ceil(150/100) = 2 | `4100-1333` | 2 |
| 7 | No telephone | — | — |
| 8 | No Class A | — | — |
| 9 | No printer, no BMS | — | — |
| 10a | 2x 4100-1333 → 2 modules | `4100-1461` | 2 |
| 10b | ceil(2/4) = 1 | `4100-1450` | 1 |
| 11 | project.network_type = wired | `4100-6078` | 1 |
| 11 | project.network_type = wired | `4100-6056` | 2 |
| 12 | Rule 4: 2x 4100-5451 → 2 PSU | `4100-5401` | 2 + 1 = 5 |
| | Rule 5: ceil(2/2) → 1 PSU | | |
| | Rule 6: ceil(8/3) → 3 PSU (rounding up 8/3=2.67) | | |
| 13 | 5 PSU → 5 extra cables | `4100-0646` | +5 (total 6) |
| 14 | ceil(5/3)=2 + ceil(2/3)=1 | `4100-0635` | +3 (total 4) |
| 15 | 5 PSU + 2 amplifiers = 7 | `4100-2300` | 7 |
| 16 | 7 bays x 8 | `4100-1279` | 56 |
| 17 | Total=7 (PSU=5 + amp=2), 7//3=2×3-bay, 7%3=1→1×1-bay | `2975-9443` | 2 |
| 17 | (remainder) | `2975-9441` | 1 |

---

## KEY DIFFERENCES: 4100ES vs 4007/4010

| Aspect | 4007 / 4010 | 4100ES |
|--------|------------|--------|
| Device range | 0-250 (4007), 250-1000 (4010) | 1000+ (or speakers/telephone/loops>6) |
| Loop capacity | 4007: up to 2 loops, 4010: up to 6 loops | More than 6 loops |
| Speakers/Telephone | Gate FAIL (not supported) | Fully supported (entry condition) |
| Loop cards | Fixed in base unit | Calculated: ceil(devices / 150 or 200) |
| NAC cards | Not separate | Calculated: ceil(hornflasher_count / 45) |
| Power supplies | Included in base unit | Calculated from card load |
| Amplifiers | Not applicable | Calculated from speaker count |
| Enclosure | Determined by range | Determined by PSU + amplifier count |
| Networking source | LLM questions Q15/Q16/Q19 | `project.network_type` from device selection |
| Child card questions | Same Q14-Q20 for all | Different set of questions (BMS, Class A, etc.) |
| Quantity logic | Simple: qty x num_panels | Complex: cascading dependencies |

---

## MISSING PRODUCTS (Not in our DB yet)

These 3 product codes from the Excel are NOT in our products table:

| Code | What It Is | Used In |
|------|-----------|---------|
| `4100-1461` | 8-Switch and 8-LED Module | Step 10 |
| `4100-1450` | LED Controller | Step 10 |
| `4100-1273` | Phone Class A NAC Adapter | Step 8c |

These will need to be added to the products table before implementation.

---

## OPEN QUESTIONS FOR ENGINEER REVIEW

1. **Row 1 "Or Condition"**: The entry gate says devices > 1000 OR speakers OR telephone.
   Does this mean the 4100ES is ONLY selected when one of these is true? Or can a
   project with < 1000 devices and no speakers/telephone still use 4100ES?

2. **Step 12 Rule 1 vs Rule 3**: Rule 1 counts groups of 6 from (3109 + 1272 + 5450).
   Rule 3 counts groups of (3109 qty 4 + 1272 + 5451 qty 1). These seem to be
   alternative formulas for IDNET with different NAC types. Should only one apply
   based on whether notification is conventional or addressable?

3. **Step 17 Enclosure**: ~~RESOLVED~~ — Uses greedy bin-packing with multiple enclosures.
   Total slots = PSU + amps, then: `total // 3` × 3-bay + remainder as 2-bay or 1-bay.
   No wasted capacity, works for any count.

4. **Multi-panel projects**: For 4007/4010, all quantities are multiplied by the number
   of panels. Does the same apply to 4100ES? Or is 4100ES always a single-panel
   configuration?

5. ~~**Speaker count source**~~: **RESOLVED** — Speaker count comes from the `subcategory`
   column on the `selectables` table. See "Subcategory System" section below.

6. **Telephone jack count source**: Where does the telephone jack count come from?
   Currently obtained via LLM question (Q206). To be updated with a DB-backed
   approach in the future.

---

## SUBCATEGORY SYSTEM (Notification Device Counting)

A nullable `subcategory` column has been added to the `selectables` table to enable
precise counting of notification device subtypes from BOQ selections.

### How it works

When a BOQ item is matched to a selectable during device selection, the selectable's
`subcategory` value determines which count that item's quantity contributes to.

### Notification subcategory values

| Subcategory | Description | Contributes to |
|---|---|---|
| `speaker` | Speaker only (no flasher) | `speaker_count` |
| `speaker_flasher` | Speaker + flasher combo | `speaker_count` AND `hornflasher_count` |
| `horn` | Horn/sounder only | `hornflasher_count` |
| `horn_flasher` | Horn + flasher/strobe combo | `hornflasher_count` |
| `flasher` | Flasher/strobe only (visual) | `hornflasher_count` |
| `strobe` | Strobe only | `hornflasher_count` |
| `strobe_flasher` | Strobe + flasher combo | `hornflasher_count` |

### Counting rules

```
speaker_count     = SUM(qty) WHERE subcategory IN ('speaker', 'speaker_flasher')
hornflasher_count = SUM(qty) WHERE subcategory IN ('speaker_flasher', 'horn',
                    'horn_flasher', 'flasher', 'strobe', 'strobe_flasher')
```

- `speaker_count` → feeds Step 6b (amplifier calculation)
- `hornflasher_count` → feeds Step 5 (NAC card calculation)
- `speaker_flasher` appears in **both** counts because the device has two functional
  parts: the speaker needs an amplifier channel, the flasher needs a NAC circuit.
- Selectables with `subcategory = NULL` (e.g., speaker covers) are skipped during counting.

### Current coverage

| Subcategory | Selectables in DB |
|---|---|
| `speaker` | 12 |
| `speaker_flasher` | 14 |
| `horn` | 6 |
| `horn_flasher` | 13 |
| `flasher` | 13 |
| `strobe` | 0 (no strobe-only devices in current data) |
| `strobe_flasher` | 0 (no strobe_flasher devices in current data) |
| NULL (covers/accessories) | 7 |
