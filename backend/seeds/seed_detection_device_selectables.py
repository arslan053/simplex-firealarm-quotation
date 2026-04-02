"""Seed script: load detection device selectables from detetction devices.xlsx."""

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
# Product code extraction (Columns A and C — messy format)
# ---------------------------------------------------------------------------

_CODE_RE = re.compile(r"[A-Z0-9][A-Z0-9.\-]+[A-Z0-9]", re.IGNORECASE)

_FILLER = {
    "vesda", "sampling", "tube", "wp", "box", "mm", "and", "with",
}


def extract_product_codes(cell_value: str) -> list[str]:
    """Extract product codes from a messy IDNet/MX cell value."""
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
# Column B: aliases parsing — multi-line with Specs directives
# ---------------------------------------------------------------------------

_SPECS_RE = re.compile(r"^specs\s*:", re.IGNORECASE)


def parse_aliases_column(cell_value: str) -> tuple[list[str], str | None]:
    """Parse Column B into (boq_match_phrases, specification_hints).

    Column B may contain multi-line content:
    - Lines without Specs prefix → BOQ match phrases (comma-separated)
    - Lines starting with 'Specs :' → specification hints
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

        if _SPECS_RE.match(stripped):
            hint_text = re.sub(r"^specs\s*:\s*", "", stripped, flags=re.IGNORECASE).strip()
            if hint_text:
                hint_parts.append(f"Refer to project specifications for: {hint_text}")
        else:
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

async def seed_detection_devices(excel_path: str):
    print(f"Reading Excel: {excel_path}")
    df = pd.read_excel(excel_path, engine="openpyxl", header=None)
    print(f"  Total rows in sheet: {df.shape[0]}")

    # Column mapping (4 columns):
    # 0 = IDNet codes (Column A)
    # 1 = aliases / boq_match_phrases + specs (Column B)
    # 2 = MX codes (Column C)
    # 3 = Description (Column D)
    # priority = always NULL, subcategory = always NULL

    rows_skipped = 0
    idnet_created = 0
    mx_created = 0
    links_created = 0
    skipped_selectables: list[dict] = []
    all_missing_codes: set[str] = set()

    async with async_session_factory() as db:
        # Idempotency: clear FK refs from boq_device_selections, then delete selectables
        nullify_result = await db.execute(text(
            "UPDATE boq_device_selections SET selectable_id = NULL "
            "WHERE selectable_id IN ("
            "  SELECT id FROM selectables WHERE category IN "
            "  ('idnet_detection_device', 'mx_detection_device')"
            ")"
        ))
        if nullify_result.rowcount:
            print(f"  Cleared {nullify_result.rowcount} boq_device_selections FK refs")

        del_result = await db.execute(text(
            "DELETE FROM selectables WHERE category IN "
            "('idnet_detection_device', 'mx_detection_device')"
        ))
        print(f"  Deleted {del_result.rowcount} existing detection device selectables")

        # Build product code -> id lookup
        result = await db.execute(text("SELECT id, code FROM products"))
        product_lookup: dict[str, str] = {row[1]: str(row[0]) for row in result}
        print(f"  Products in DB: {len(product_lookup)}")

        for idx in range(1, len(df)):  # skip header row 0
            row = df.iloc[idx]
            col_idnet = row.iloc[0]   # Column A — IDNet codes
            col_alias = row.iloc[1]   # Column B — aliases + specs
            col_mx = row.iloc[2]      # Column C — MX codes
            col_desc = row.iloc[3] if df.shape[1] > 3 else None  # Column D — Description

            # Parse aliases and specs from Column B
            boq_phrases, spec_hints = parse_aliases_column(col_alias)
            description = safe_str(col_desc)

            # Extract product codes from both sides
            idnet_codes = extract_product_codes(col_idnet)
            mx_codes = extract_product_codes(col_mx)

            # Skip fully empty rows
            if not boq_phrases and not idnet_codes and not mx_codes:
                rows_skipped += 1
                continue

            # Skip rows where aliases exist but no codes on either side
            if boq_phrases and not idnet_codes and not mx_codes:
                rows_skipped += 1
                continue

            row_num = idx + 1  # Excel row number (1-indexed, header is row 1)

            # --- Process IDNet side ---
            if idnet_codes:
                matched_pids: list[str] = []
                unmatched: list[str] = []
                for code in idnet_codes:
                    pid = product_lookup.get(code)
                    if pid:
                        matched_pids.append(pid)
                    else:
                        unmatched.append(code)

                if unmatched:
                    all_missing_codes.update(unmatched)
                    skipped_selectables.append({
                        "row": row_num,
                        "side": "IDNet",
                        "all_codes": idnet_codes,
                        "missing_codes": unmatched,
                        "description": description or "",
                    })
                else:
                    sel_type = "single" if len(idnet_codes) <= 1 else "combo"
                    result = await db.execute(
                        text("""
                            INSERT INTO selectables
                                (category, selection_type, boq_match_phrases, description,
                                 specification_hints, priority, subcategory)
                            VALUES
                                ('idnet_detection_device', :sel_type, :phrases, :description,
                                 :spec_hints, NULL, NULL)
                            RETURNING id
                        """),
                        {
                            "sel_type": sel_type,
                            "phrases": boq_phrases,
                            "description": description,
                            "spec_hints": spec_hints,
                        },
                    )
                    sel_id = str(result.scalar())
                    idnet_created += 1

                    for pid in matched_pids:
                        await db.execute(
                            text("""
                                INSERT INTO selectable_products (selectable_id, product_id)
                                VALUES (:sel_id, :pid)
                            """),
                            {"sel_id": sel_id, "pid": pid},
                        )
                        links_created += 1

            # --- Process MX side ---
            if mx_codes:
                matched_pids = []
                unmatched = []
                for code in mx_codes:
                    pid = product_lookup.get(code)
                    if pid:
                        matched_pids.append(pid)
                    else:
                        unmatched.append(code)

                if unmatched:
                    all_missing_codes.update(unmatched)
                    skipped_selectables.append({
                        "row": row_num,
                        "side": "MX",
                        "all_codes": mx_codes,
                        "missing_codes": unmatched,
                        "description": description or "",
                    })
                else:
                    sel_type = "single" if len(mx_codes) <= 1 else "combo"
                    result = await db.execute(
                        text("""
                            INSERT INTO selectables
                                (category, selection_type, boq_match_phrases, description,
                                 specification_hints, priority, subcategory)
                            VALUES
                                ('mx_detection_device', :sel_type, :phrases, :description,
                                 :spec_hints, NULL, NULL)
                            RETURNING id
                        """),
                        {
                            "sel_type": sel_type,
                            "phrases": boq_phrases,
                            "description": description,
                            "spec_hints": spec_hints,
                        },
                    )
                    sel_id = str(result.scalar())
                    mx_created += 1

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
    print(f"  Total Excel rows:              {df.shape[0]}")
    print(f"  Rows skipped (empty):          {rows_skipped}")
    print(f"  IDNet selectables created:     {idnet_created}")
    print(f"  MX selectables created:        {mx_created}")
    print(f"  Total selectables:             {idnet_created + mx_created}")
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
            print(f"  Side:          {entry['side']}")
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
                   s.specification_hints, s.description, s.priority,
                   COALESCE(array_agg(p.code) FILTER (WHERE p.code IS NOT NULL), '{}') AS product_codes
            FROM selectables s
            LEFT JOIN selectable_products sp ON sp.selectable_id = s.id
            LEFT JOIN products p ON p.id = sp.product_id
            WHERE s.category IN ('idnet_detection_device', 'mx_detection_device')
            GROUP BY s.id, s.category, s.selection_type, s.boq_match_phrases,
                     s.specification_hints, s.description, s.priority
            ORDER BY s.category, s.created_at
            LIMIT 5
        """))
        for row in result:
            phrases = row[2][:3] if row[2] else []
            print(f"\n  Category:          {row[0]}")
            print(f"  Selection type:    {row[1]}")
            print(f"  BOQ match phrases: {phrases}")
            print(f"  Spec hints:        {row[3] or '(none)'}")
            print(f"  Description:       {row[4] or '(none)'}")
            print(f"  Priority:          {row[5] or '(none)'}")
            print(f"  Product codes:     {row[6]}")

    # =====================================================================
    # DB VERIFICATION
    # =====================================================================
    async with async_session_factory() as db:
        r = await db.execute(text(
            "SELECT category, COUNT(*) FROM selectables "
            "WHERE category IN ('idnet_detection_device', 'mx_detection_device') "
            "GROUP BY category ORDER BY category"
        ))
        print(f"\n--- DB Verification ---")
        for row in r:
            print(f"  {row[0]}: {row[1]} selectables")

        r = await db.execute(text(
            "SELECT COUNT(*) FROM selectable_products sp "
            "JOIN selectables s ON s.id = sp.selectable_id "
            "WHERE s.category IN ('idnet_detection_device', 'mx_detection_device')"
        ))
        print(f"  Total junction links: {r.scalar()}")

        # Check no selectables have zero links
        r = await db.execute(text("""
            SELECT s.id, s.description, s.category
            FROM selectables s
            LEFT JOIN selectable_products sp ON sp.selectable_id = s.id
            WHERE s.category IN ('idnet_detection_device', 'mx_detection_device')
            GROUP BY s.id, s.description, s.category
            HAVING COUNT(sp.product_id) = 0
        """))
        orphans = r.fetchall()
        if orphans:
            print(f"\n  WARNING: {len(orphans)} selectables with ZERO product links!")
            for o in orphans:
                print(f"    - [{o[2]}] {o[1]} (id: {o[0]})")
        else:
            print("  All selectables have product links -- OK")


async def main():
    parser = argparse.ArgumentParser(description="Seed detection device selectables")
    parser.add_argument(
        "excel_path",
        nargs="?",
        default=os.path.join(os.path.dirname(__file__), "..", "..", "detetction devices.xlsx"),
        help="Path to detetction devices.xlsx",
    )
    args = parser.parse_args()

    try:
        await seed_detection_devices(args.excel_path)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
