"""Seed script: load annunciator & subpanel selectables from Annunciators-Subpanels.xlsx."""

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
# Column C: aliases parsing — multi-line with Specs/Note directives
# ---------------------------------------------------------------------------

_SPEC_NOTE_RE = re.compile(r"^(specs|note)\s*:", re.IGNORECASE)


def parse_aliases_column(cell_value: str) -> tuple[list[str], str | None]:
    """Parse Column C into (boq_match_phrases, specification_hints).

    Column C may contain multi-line content:
    - First line(s) without Specs/Note prefix → BOQ match phrases (comma-separated)
    - Lines starting with 'Specs :' or 'Note :' → specification hints
    """
    if pd.isna(cell_value) or str(cell_value).strip().lower() == "nan":
        return [], None

    raw = str(cell_value).strip()
    lines = raw.split("\n")

    phrase_parts: list[str] = []
    hint_parts: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if _SPEC_NOTE_RE.match(stripped):
            # Extract the text after "Specs :" or "Note :"
            hint_text = re.sub(r"^(specs|note)\s*:\s*", "", stripped, flags=re.IGNORECASE).strip()
            if hint_text:
                hint_parts.append(f"Refer to project specifications for: {hint_text}")
        else:
            # BOQ match phrases line — split by comma
            for part in stripped.split(","):
                p = part.strip().rstrip(".").strip()
                if p:
                    phrase_parts.append(p)

    # Deduplicate phrases preserving order
    phrases: list[str] = []
    seen: set[str] = set()
    for p in phrase_parts:
        if p.lower() not in seen:
            seen.add(p.lower())
            phrases.append(p)

    spec_hints = " | ".join(hint_parts) if hint_parts else None

    return phrases, spec_hints


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

async def seed_annunciator_subpanels(excel_path: str):
    print(f"Reading Excel: {excel_path}")
    df = pd.read_excel(excel_path, engine="openpyxl")
    print(f"  Rows in sheet: {len(df)}")
    print(f"  Columns: {list(df.columns)}")

    # Column mapping (6 columns):
    # 0=S.No, 1=Part Numbers, 2=aliases (boq_match_phrases + spec hints),
    # 3=Description, 4=Sub category, 5=Priority
    # category = always 'annunciator_subpanel'

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
            "  SELECT id FROM selectables WHERE category = 'annunciator_subpanel'"
            ")"
        ))
        if nullify_result.rowcount:
            print(f"  Cleared {nullify_result.rowcount} boq_device_selections FK refs")

        del_result = await db.execute(text(
            "DELETE FROM selectables WHERE category = 'annunciator_subpanel'"
        ))
        print(f"  Deleted {del_result.rowcount} existing annunciator_subpanel selectables")

        # Build product code -> id lookup
        result = await db.execute(text("SELECT id, code FROM products"))
        product_lookup: dict[str, str] = {row[1]: str(row[0]) for row in result}
        print(f"  Products in DB: {len(product_lookup)}")

        for idx, row in df.iterrows():
            row_num = idx + 2  # Excel row number (header is row 1)

            # Read columns by position
            raw_part_numbers = row.iloc[1] if len(row) > 1 else None
            raw_aliases = row.iloc[2] if len(row) > 2 else None
            raw_description = row.iloc[3] if len(row) > 3 else None
            raw_subcategory = row.iloc[4] if len(row) > 4 else None
            raw_priority = row.iloc[5] if len(row) > 5 else None

            product_codes = extract_product_codes(raw_part_numbers)
            boq_phrases, spec_hints = parse_aliases_column(raw_aliases)
            description = safe_str(raw_description)
            subcategory = safe_str(raw_subcategory)
            priority = safe_str(raw_priority)
            if priority:
                priority = priority.capitalize()

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
                    "subcategory": subcategory or "",
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
                        ('annunciator_subpanel', :sel_type, :phrases, :description,
                         :spec_hints, :priority, :subcategory)
                    RETURNING id
                """),
                {
                    "sel_type": sel_type,
                    "phrases": boq_phrases,
                    "description": description,
                    "spec_hints": spec_hints,
                    "priority": priority,
                    "subcategory": subcategory,
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
    print(f"  Selectables created:           {selectables_created}")
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
            print(f"  Subcategory:   {entry['subcategory']}")

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
    # SAMPLE RECORDS (show all)
    # =====================================================================
    print(f"\n--- All Records ---")
    async with async_session_factory() as db:
        result = await db.execute(text("""
            SELECT s.category, s.selection_type, s.boq_match_phrases,
                   s.specification_hints, s.description, s.subcategory, s.priority,
                   COALESCE(array_agg(p.code) FILTER (WHERE p.code IS NOT NULL), '{}') AS product_codes
            FROM selectables s
            LEFT JOIN selectable_products sp ON sp.selectable_id = s.id
            LEFT JOIN products p ON p.id = sp.product_id
            WHERE s.category = 'annunciator_subpanel'
            GROUP BY s.id, s.category, s.selection_type, s.boq_match_phrases,
                     s.specification_hints, s.description, s.subcategory, s.priority
            ORDER BY s.created_at
        """))
        for row in result:
            phrases = row[2][:4] if row[2] else []
            print(f"\n  Category:          {row[0]}")
            print(f"  Selection type:    {row[1]}")
            print(f"  BOQ match phrases: {phrases}")
            print(f"  Spec hints:        {row[3] or '(none)'}")
            print(f"  Description:       {row[4] or '(none)'}")
            print(f"  Subcategory:       {row[5] or '(none)'}")
            print(f"  Priority:          {row[6] or '(none)'}")
            print(f"  Product codes:     {row[7]}")

    # =====================================================================
    # DB VERIFICATION
    # =====================================================================
    async with async_session_factory() as db:
        r = await db.execute(text(
            "SELECT COUNT(*) FROM selectables WHERE category = 'annunciator_subpanel'"
        ))
        print(f"\n--- DB Verification ---")
        print(f"  annunciator_subpanel selectables: {r.scalar()}")

        r = await db.execute(text(
            "SELECT COUNT(*) FROM selectable_products sp "
            "JOIN selectables s ON s.id = sp.selectable_id "
            "WHERE s.category = 'annunciator_subpanel'"
        ))
        print(f"  Total junction links: {r.scalar()}")

        # Check no selectables have zero links
        r = await db.execute(text("""
            SELECT s.id, s.description
            FROM selectables s
            LEFT JOIN selectable_products sp ON sp.selectable_id = s.id
            WHERE s.category = 'annunciator_subpanel'
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
    parser = argparse.ArgumentParser(description="Seed annunciator & subpanel selectables")
    parser.add_argument(
        "excel_path",
        nargs="?",
        default=os.path.join(os.path.dirname(__file__), "..", "..", "Annunciators-Subpanels.xlsx"),
        help="Path to Annunciators-Subpanels.xlsx",
    )
    args = parser.parse_args()

    try:
        await seed_annunciator_subpanels(args.excel_path)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
