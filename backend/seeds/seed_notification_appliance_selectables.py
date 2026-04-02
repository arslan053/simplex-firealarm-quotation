"""Seed script: load notification appliance selectables from notifications_with_subcategories.xlsx."""

import argparse
import asyncio
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.database import async_session_factory, engine


# ---------------------------------------------------------------------------
# Section header detection
# ---------------------------------------------------------------------------

def detect_section(cell_value: str) -> str | None:
    """Return category enum if this cell is a section header, else None."""
    lower = cell_value.strip().lower()
    # Check non-addressable first (more specific) before addressable
    if "non-addressable" in lower and "notification" in lower:
        return "non_addressable_notification_device"
    if "addressable" in lower and "notification" in lower:
        return "addressable_notification_device"
    return None


# ---------------------------------------------------------------------------
# Product code extraction
# ---------------------------------------------------------------------------

_CODE_RE = re.compile(r"[A-Z0-9][A-Z0-9.\-]+[A-Z0-9]", re.IGNORECASE)

_FILLER = {
    "vesda", "sampling", "tube", "wp", "box", "mm", "and", "with",
}


def extract_product_codes(cell_value: str) -> list[str]:
    """Extract product codes from a messy cell value."""
    if pd.isna(cell_value) or str(cell_value).strip().lower() == "nan":
        return []

    s = str(cell_value).strip()
    s = re.sub(r"\([^)]*\)", " ", s)
    for sep in ["and", "with"]:
        s = re.sub(rf"\b{sep}\b", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"[,;&/|]", " ", s)
    s = s.replace("\n", " ")

    tokens = _CODE_RE.findall(s)
    codes: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token.lower() in _FILLER:
            continue
        if len(token) < 3:
            continue
        if token not in seen:
            seen.add(token)
            codes.append(token)
    return codes


# ---------------------------------------------------------------------------
# Aliases parsing (Column C → boq_match_phrases)
# ---------------------------------------------------------------------------

def parse_aliases(cell_value: str) -> list[str]:
    """Split aliases cell into a list of trimmed synonyms (boq_match_phrases)."""
    if pd.isna(cell_value) or str(cell_value).strip().lower() == "nan":
        return []

    raw = str(cell_value).strip()
    parts = [p.strip().rstrip(".").strip() for p in raw.split(",")]

    # Remove empty strings, deduplicate preserving order
    phrases: list[str] = []
    seen: set[str] = set()
    for p in parts:
        if p and p.lower() not in seen:
            seen.add(p.lower())
            phrases.append(p)

    return phrases


# ---------------------------------------------------------------------------
# Helper: safe string extraction from cell
# ---------------------------------------------------------------------------

def safe_str(cell_value) -> str | None:
    """Return stripped string or None for NaN/empty."""
    if pd.isna(cell_value) or cell_value is None:
        return None
    s = str(cell_value).strip()
    if s.lower() in ("nan", ""):
        return None
    return s


# ---------------------------------------------------------------------------
# Main seed logic
# ---------------------------------------------------------------------------

async def seed_notification_appliances(excel_path: str):
    print(f"Reading Excel: {excel_path}")
    df = pd.read_excel(excel_path, engine="openpyxl", header=None)
    print(f"  Total rows in sheet: {df.shape[0]}")

    # Column mapping (9 columns):
    # 0=S.No, 1=Part Numbers, 2=Aliases (boq_match_phrases), 3=Description.1,
    # 4=Colour, 5=Mounting Type, 6=Final Description, 7=Priority, 8=Subcategory
    # specification_hints = always NULL

    current_category: str | None = None
    rows_skipped = 0
    non_addr_created = 0
    addr_created = 0
    links_created = 0
    skipped_selectables: list[dict] = []
    all_missing_codes: set[str] = set()

    async with async_session_factory() as db:
        # Idempotency: clear FK refs from boq_device_selections, then delete selectables
        nullify_result = await db.execute(text(
            "UPDATE boq_device_selections SET selectable_id = NULL "
            "WHERE selectable_id IN ("
            "  SELECT id FROM selectables WHERE category IN "
            "  ('non_addressable_notification_device', 'addressable_notification_device')"
            ")"
        ))
        if nullify_result.rowcount:
            print(f"  Cleared {nullify_result.rowcount} boq_device_selections FK refs")

        del_result = await db.execute(text(
            "DELETE FROM selectables WHERE category IN "
            "('non_addressable_notification_device', 'addressable_notification_device')"
        ))
        print(f"  Deleted {del_result.rowcount} existing notification selectables")

        # Build product code → id lookup
        result = await db.execute(text("SELECT id, code FROM products"))
        product_lookup: dict[str, str] = {row[1]: str(row[0]) for row in result}
        print(f"  Products in DB: {len(product_lookup)}")

        for idx in range(1, len(df)):  # skip header row 0
            row = df.iloc[idx]
            col_a = row.iloc[0]                                        # S.No or section header
            col_b = row.iloc[1]                                        # Part Number(s)
            col_c = row.iloc[2]                                        # Aliases
            col_final = row.iloc[6] if df.shape[1] > 6 else None      # Final Description
            col_priority = row.iloc[7] if df.shape[1] > 7 else None   # Priority
            col_subcategory = row.iloc[8] if df.shape[1] > 8 else None  # Subcategory

            col_a_str = str(col_a).strip() if not pd.isna(col_a) else ""

            # Check if this is a section header
            if col_a_str:
                section = detect_section(col_a_str)
                if section:
                    current_category = section
                    print(f"  Section: {col_a_str} -> {current_category}")
                    rows_skipped += 1
                    continue

            # Skip fully empty rows
            if pd.isna(col_b) and pd.isna(col_c):
                rows_skipped += 1
                continue

            # Must have a category by now
            if current_category is None:
                rows_skipped += 1
                continue

            # Extract product codes from part number cell
            part_codes = extract_product_codes(col_b)
            boq_match_phrases = parse_aliases(col_c)

            # Skip rows with no aliases and no part codes
            if not boq_match_phrases and not part_codes:
                rows_skipped += 1
                continue

            # Final description (display text) from Column G
            final_desc = safe_str(col_final)

            # Priority from Column H
            priority = safe_str(col_priority)
            if priority:
                priority = priority.capitalize()  # Normalize to "High"

            # Subcategory from Column I
            subcategory = safe_str(col_subcategory)

            # Determine selection type based on number of product codes
            sel_type = "single" if len(part_codes) <= 1 else "combo"

            # --- CRITICAL: Pre-check ALL product codes must exist ---
            matched_pids: list[str] = []
            unmatched_codes: list[str] = []
            for code in part_codes:
                pid = product_lookup.get(code)
                if pid:
                    matched_pids.append(pid)
                else:
                    unmatched_codes.append(code)

            # If ANY code is missing -> SKIP the entire selectable
            if unmatched_codes:
                all_missing_codes.update(unmatched_codes)
                skipped_selectables.append({
                    "row": idx + 1,
                    "all_codes": part_codes,
                    "missing_codes": unmatched_codes,
                    "aliases": str(col_c).strip() if not pd.isna(col_c) else "",
                    "final_description": final_desc or "",
                    "category": current_category,
                })
                rows_skipped += 1
                continue

            # All codes found -> create the selectable
            result = await db.execute(
                text("""
                    INSERT INTO selectables
                        (category, selection_type, boq_match_phrases, description,
                         specification_hints, priority, subcategory)
                    VALUES
                        (:category, :sel_type, :phrases, :description,
                         NULL, :priority, :subcategory)
                    RETURNING id
                """),
                {
                    "category": current_category,
                    "sel_type": sel_type,
                    "phrases": boq_match_phrases,
                    "description": final_desc,
                    "priority": priority,
                    "subcategory": subcategory,
                },
            )
            sel_id = str(result.scalar())

            # Create junction records for ALL matched products
            for pid in matched_pids:
                await db.execute(
                    text("""
                        INSERT INTO selectable_products (selectable_id, product_id)
                        VALUES (:sel_id, :pid)
                    """),
                    {"sel_id": sel_id, "pid": pid},
                )
                links_created += 1

            if current_category == "non_addressable_notification_device":
                non_addr_created += 1
            else:
                addr_created += 1

        await db.commit()

    # =====================================================================
    # SEED SUMMARY
    # =====================================================================
    print(f"\n{'='*60}")
    print("SEED SUMMARY")
    print(f"{'='*60}")
    print(f"  Total Excel rows:                    {df.shape[0]}")
    print(f"  Rows skipped (empty/header/missing): {rows_skipped}")
    print(f"  Non-addressable selectables created:  {non_addr_created}")
    print(f"  Addressable selectables created:      {addr_created}")
    print(f"  Total selectables created:            {non_addr_created + addr_created}")
    print(f"  Product links created:                {links_created}")
    print(f"  Selectables SKIPPED (missing prods):  {len(skipped_selectables)}")

    # =====================================================================
    # SKIPPED SELECTABLES REPORT
    # =====================================================================
    if skipped_selectables:
        print(f"\n{'='*60}")
        print("SKIPPED SELECTABLES -- not created because some product codes missing")
        print(f"{'='*60}")
        for entry in skipped_selectables:
            print(f"\n  Row:               {entry['row']}")
            print(f"  All codes:         {entry['all_codes']}")
            print(f"  Missing codes:     {entry['missing_codes']}")
            print(f"  Aliases:           {entry['aliases']}")
            print(f"  Final Description: {entry['final_description']}")
            print(f"  Category:          {entry['category']}")

    # =====================================================================
    # MISSING PRODUCTS LIST (deduplicated)
    # =====================================================================
    if all_missing_codes:
        print(f"\n{'='*60}")
        print(f"MISSING PRODUCTS LIST -- {len(all_missing_codes)} unique codes not in products table")
        print(f"{'='*60}")
        for code in sorted(all_missing_codes):
            print(f"  - {code}")
    else:
        print("\nAll product codes found -- no missing products!")

    # =====================================================================
    # SAMPLE RECORDS (verification)
    # =====================================================================
    async with async_session_factory() as db:
        result = await db.execute(text("""
            SELECT s.category, s.selection_type, s.boq_match_phrases,
                   s.description, s.specification_hints, s.priority, s.subcategory,
                   COALESCE(array_agg(p.code) FILTER (WHERE p.code IS NOT NULL), '{}') AS product_codes
            FROM selectables s
            LEFT JOIN selectable_products sp ON sp.selectable_id = s.id
            LEFT JOIN products p ON p.id = sp.product_id
            WHERE s.category IN ('non_addressable_notification_device', 'addressable_notification_device')
            GROUP BY s.id, s.category, s.selection_type, s.boq_match_phrases,
                     s.description, s.specification_hints, s.priority, s.subcategory
            ORDER BY s.category, s.created_at
            LIMIT 5
        """))
        rows = result.fetchall()
        if rows:
            print(f"\n--- Sample Records ---")
            for row in rows:
                phrases = row[2][:3] if row[2] else []
                print(f"\n  Category:          {row[0]}")
                print(f"  Selection type:    {row[1]}")
                print(f"  BOQ match phrases: {phrases}")
                print(f"  Description:       {row[3] or '(none)'}")
                print(f"  Spec hints:        {row[4] or '(none)'}")
                print(f"  Priority:          {row[5] or '(none)'}")
                print(f"  Subcategory:       {row[6] or '(none)'}")
                print(f"  Product codes:     {row[7]}")

    # =====================================================================
    # VERIFICATION COUNTS
    # =====================================================================
    async with async_session_factory() as db:
        r = await db.execute(text(
            "SELECT category, COUNT(*) FROM selectables "
            "WHERE category IN ('non_addressable_notification_device','addressable_notification_device') "
            "GROUP BY category ORDER BY category"
        ))
        print(f"\n--- DB Verification ---")
        for row in r:
            print(f"  {row[0]}: {row[1]} selectables")

        r = await db.execute(text(
            "SELECT COUNT(*) FROM selectable_products sp "
            "JOIN selectables s ON s.id = sp.selectable_id "
            "WHERE s.category IN ('non_addressable_notification_device','addressable_notification_device')"
        ))
        print(f"  Total junction links: {r.scalar()}")

        # Check no selectables have zero links (all should have full product links)
        r = await db.execute(text("""
            SELECT s.id, s.description
            FROM selectables s
            LEFT JOIN selectable_products sp ON sp.selectable_id = s.id
            WHERE s.category IN ('non_addressable_notification_device','addressable_notification_device')
            GROUP BY s.id, s.description
            HAVING COUNT(sp.product_id) = 0
        """))
        orphans = r.fetchall()
        if orphans:
            print(f"\n  WARNING: {len(orphans)} selectables with ZERO product links!")
            for o in orphans:
                print(f"    - {o[1]} (id: {o[0]})")
        else:
            print("  All selectables have product links -- OK")


async def main():
    parser = argparse.ArgumentParser(description="Seed notification appliance selectables")
    parser.add_argument(
        "excel_path",
        nargs="?",
        default=os.path.join(os.path.dirname(__file__), "..", "..", "notifications_with_subcategories.xlsx"),
        help="Path to notifications_with_subcategories.xlsx",
    )
    args = parser.parse_args()

    try:
        await seed_notification_appliances(args.excel_path)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
