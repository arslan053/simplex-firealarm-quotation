"""Seed script: load conventional device selectables from Conventional devices.xlsx."""

import argparse
import asyncio
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.database import async_session_factory, engine


# ---------------------------------------------------------------------------
# Column B: product codes (newline-separated)
# ---------------------------------------------------------------------------

def extract_product_codes(cell_value: str) -> list[str]:
    """Extract product codes from Column B (newline-separated)."""
    if pd.isna(cell_value) or str(cell_value).strip().lower() == "nan":
        return []

    s = str(cell_value).strip()
    lines = s.split("\n")

    codes: list[str] = []
    seen: set[str] = set()
    for line in lines:
        code = line.strip()
        if code and code not in seen:
            seen.add(code)
            codes.append(code)

    return codes


# ---------------------------------------------------------------------------
# Column C: aliases → boq_match_phrases (comma-separated)
# ---------------------------------------------------------------------------

def extract_boq_phrases(cell_value: str) -> list[str]:
    """Extract BOQ match phrases from Column C (comma-separated aliases)."""
    if pd.isna(cell_value) or str(cell_value).strip().lower() == "nan":
        return []

    raw = str(cell_value).strip()
    parts = [p.strip().rstrip(".").strip() for p in raw.split(",")]

    phrases: list[str] = []
    seen: set[str] = set()
    for p in parts:
        if p and p.lower() not in seen:
            seen.add(p.lower())
            phrases.append(p)

    return phrases


# ---------------------------------------------------------------------------
# Column D: description
# ---------------------------------------------------------------------------

def extract_description(cell_value: str) -> str | None:
    """Extract description from Column D."""
    if pd.isna(cell_value) or str(cell_value).strip().lower() == "nan":
        return None
    return str(cell_value).strip() or None


# ---------------------------------------------------------------------------
# Main seed logic
# ---------------------------------------------------------------------------

async def seed_conventional_devices(excel_path: str):
    print(f"Reading Excel: {excel_path}")
    df = pd.read_excel(excel_path, engine="openpyxl")
    print(f"  Rows in sheet: {len(df)}")
    print(f"  Columns: {list(df.columns)}")

    # Counters
    rows_skipped = 0
    selectables_created = 0
    single_count = 0
    combo_count = 0
    links_created = 0
    skipped_selectables: list[dict] = []
    all_missing_codes: set[str] = set()

    async with async_session_factory() as db:
        # Idempotency: clear FK refs from boq_device_selections, then delete selectables
        nullify_result = await db.execute(text(
            "UPDATE boq_device_selections SET selectable_id = NULL "
            "WHERE selectable_id IN ("
            "  SELECT id FROM selectables WHERE category = 'conventional_device'"
            ")"
        ))
        if nullify_result.rowcount:
            print(f"  Cleared {nullify_result.rowcount} boq_device_selections FK refs")

        del_result = await db.execute(text(
            "DELETE FROM selectables WHERE category = 'conventional_device'"
        ))
        print(f"  Deleted {del_result.rowcount} existing conventional selectables")

        # Build a code->id lookup from products table
        result = await db.execute(text("SELECT id, code FROM products"))
        product_lookup: dict[str, str] = {row[1]: str(row[0]) for row in result}
        print(f"  Products in DB: {len(product_lookup)}")

        for idx, row in df.iterrows():
            row_num = idx + 2  # Excel row number (header is row 1)

            # Read columns by position (A=0, B=1, C=2, D=3)
            raw_part_numbers = row.iloc[1] if len(row) > 1 else None
            raw_aliases = row.iloc[2] if len(row) > 2 else None
            raw_description = row.iloc[3] if len(row) > 3 else None

            product_codes = extract_product_codes(raw_part_numbers)
            boq_phrases = extract_boq_phrases(raw_aliases)
            description = extract_description(raw_description)

            # Skip empty rows
            if not product_codes and not boq_phrases:
                rows_skipped += 1
                continue

            # Determine selection type
            sel_type = "single" if len(product_codes) <= 1 else "combo"

            # --- CRITICAL: Pre-check ALL product codes must exist ---
            matched_pids: list[str] = []
            unmatched_codes: list[str] = []
            for code in product_codes:
                pid = product_lookup.get(code)
                if pid:
                    matched_pids.append(pid)
                else:
                    unmatched_codes.append(code)

            # If ANY code is missing -> SKIP the entire selectable
            if unmatched_codes:
                all_missing_codes.update(unmatched_codes)
                skipped_selectables.append({
                    "row": row_num,
                    "all_codes": product_codes,
                    "missing_codes": unmatched_codes,
                    "description": description or "",
                })
                rows_skipped += 1
                continue

            # All codes found -> create the selectable
            result = await db.execute(
                text("""
                    INSERT INTO selectables
                        (category, selection_type, boq_match_phrases, description,
                         specification_hints, priority)
                    VALUES
                        ('conventional_device', :sel_type, :phrases, :description,
                         NULL, NULL)
                    RETURNING id
                """),
                {
                    "sel_type": sel_type,
                    "phrases": boq_phrases,
                    "description": description,
                },
            )
            sel_id = str(result.scalar())
            selectables_created += 1
            if sel_type == "single":
                single_count += 1
            else:
                combo_count += 1

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

        await db.commit()

    # =====================================================================
    # SEED SUMMARY
    # =====================================================================
    print(f"\n{'='*60}")
    print("SEED SUMMARY")
    print(f"{'='*60}")
    print(f"  Total Excel rows:              {len(df)}")
    print(f"  Rows skipped (empty/missing):  {rows_skipped}")
    print(f"  Conventional selectables:      {selectables_created}")
    print(f"    Single:                      {single_count}")
    print(f"    Combo:                       {combo_count}")
    print(f"  Product links created:         {links_created}")
    print(f"  Selectables SKIPPED:           {len(skipped_selectables)}")

    # =====================================================================
    # SKIPPED SELECTABLES REPORT
    # =====================================================================
    if skipped_selectables:
        print(f"\n{'='*60}")
        print("SKIPPED SELECTABLES -- not created because some product codes missing")
        print(f"{'='*60}")
        for entry in skipped_selectables:
            print(f"\n  Row:           {entry['row']}")
            print(f"  All codes:     {entry['all_codes']}")
            print(f"  Missing codes: {entry['missing_codes']}")
            print(f"  Description:   {entry['description']}")

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
    # SAMPLE RECORDS
    # =====================================================================
    print(f"\n--- Sample Records ---")
    async with async_session_factory() as db:
        result = await db.execute(text("""
            SELECT s.category, s.selection_type, s.boq_match_phrases,
                   s.description, s.specification_hints, s.priority,
                   COALESCE(array_agg(p.code) FILTER (WHERE p.code IS NOT NULL), '{}') AS product_codes
            FROM selectables s
            LEFT JOIN selectable_products sp ON sp.selectable_id = s.id
            LEFT JOIN products p ON p.id = sp.product_id
            WHERE s.category = 'conventional_device'
            GROUP BY s.id, s.category, s.selection_type, s.boq_match_phrases,
                     s.description, s.specification_hints, s.priority
            ORDER BY s.created_at
            LIMIT 5
        """))
        for row in result:
            phrases = row[2][:3] if row[2] else []
            print(f"\n  Category:          {row[0]}")
            print(f"  Selection type:    {row[1]}")
            print(f"  BOQ match phrases: {phrases}")
            print(f"  Description:       {row[3] or '(none)'}")
            print(f"  Spec hints:        {row[4] or '(none)'}")
            print(f"  Priority:          {row[5] or '(none)'}")
            print(f"  Product codes:     {row[6]}")

    # =====================================================================
    # DB VERIFICATION
    # =====================================================================
    async with async_session_factory() as db:
        r = await db.execute(text(
            "SELECT COUNT(*) FROM selectables WHERE category = 'conventional_device'"
        ))
        print(f"\n--- DB Verification ---")
        print(f"  conventional_device selectables: {r.scalar()}")

        r = await db.execute(text(
            "SELECT COUNT(*) FROM selectable_products sp "
            "JOIN selectables s ON s.id = sp.selectable_id "
            "WHERE s.category = 'conventional_device'"
        ))
        print(f"  Total junction links: {r.scalar()}")

        # Check no selectables have zero links
        r = await db.execute(text("""
            SELECT s.id, s.description
            FROM selectables s
            LEFT JOIN selectable_products sp ON sp.selectable_id = s.id
            WHERE s.category = 'conventional_device'
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
    parser = argparse.ArgumentParser(description="Seed conventional device selectables")
    parser.add_argument(
        "excel_path",
        nargs="?",
        default=os.path.join(os.path.dirname(__file__), "..", "..", "Conventional devices.xlsx"),
        help="Path to Conventional devices.xlsx",
    )
    args = parser.parse_args()

    try:
        await seed_conventional_devices(args.excel_path)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
