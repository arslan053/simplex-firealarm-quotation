"""Update subcategory on notification selectables from notifications_with_subcategories.xlsx.

Matches each xlsx row to its selectable via product codes in the
selectable_products → products junction. Only updates rows where
subcategory is not null in the xlsx.
"""

import asyncio
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.database import async_session_factory, engine

_CODE_RE = re.compile(r"[A-Z0-9][A-Z0-9.\-]+[A-Z0-9]", re.IGNORECASE)
_FILLER = {"vesda", "sampling", "tube", "wp", "box", "mm", "and", "with"}


def extract_product_codes(cell_value) -> list[str]:
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


async def update_subcategories():
    xlsx_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "notifications_with_subcategories.xlsx"
    )
    print(f"Reading: {xlsx_path}")
    df = pd.read_excel(xlsx_path, engine="openpyxl", header=None)
    print(f"  Total rows: {df.shape[0]}, Columns: {df.shape[1]}")

    # Collect rows with subcategory (column I = index 8)
    updates: list[dict] = []
    for idx in range(1, len(df)):
        row = df.iloc[idx]
        subcategory = row.iloc[8] if df.shape[1] > 8 else None
        if pd.isna(subcategory) or str(subcategory).strip().lower() in ("", "nan"):
            continue
        part_numbers = row.iloc[1]
        codes = extract_product_codes(part_numbers)
        if not codes:
            continue
        final_desc = row.iloc[6] if df.shape[1] > 6 and not pd.isna(row.iloc[6]) else ""
        updates.append({
            "row": idx + 1,
            "codes": codes,
            "subcategory": str(subcategory).strip(),
            "description": str(final_desc).strip(),
        })

    print(f"  Rows with subcategory: {len(updates)}")

    async with async_session_factory() as db:
        # Build product code → selectable_id lookup
        result = await db.execute(text("""
            SELECT p.code, sp.selectable_id
            FROM selectable_products sp
            JOIN products p ON p.id = sp.product_id
            JOIN selectables s ON s.id = sp.selectable_id
            WHERE s.category IN (
                'addressable_notification_device',
                'non_addressable_notification_device'
            )
        """))
        code_to_selectable: dict[str, str] = {}
        for row in result.fetchall():
            code_to_selectable[row[0]] = str(row[1])

        print(f"  Product code → selectable mappings: {len(code_to_selectable)}")

        updated = 0
        not_found: list[dict] = []

        for entry in updates:
            # Find selectable by matching ANY product code from this row
            sel_id = None
            matched_code = None
            for code in entry["codes"]:
                if code in code_to_selectable:
                    sel_id = code_to_selectable[code]
                    matched_code = code
                    break

            if not sel_id:
                not_found.append(entry)
                continue

            await db.execute(
                text("UPDATE selectables SET subcategory = :sub WHERE id = :sid"),
                {"sub": entry["subcategory"], "sid": sel_id},
            )
            updated += 1
            print(
                f"  [OK] Row {entry['row']}: {matched_code} → "
                f"subcategory={entry['subcategory']}  ({entry['description'][:50]})"
            )

        await db.commit()

    # Summary
    print(f"\n{'=' * 60}")
    print(f"UPDATE SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Rows with subcategory in xlsx:  {len(updates)}")
    print(f"  Selectables updated:            {updated}")
    print(f"  Not found in DB:                {len(not_found)}")

    if not_found:
        print(f"\n{'=' * 60}")
        print(f"NOT FOUND — these xlsx rows had no matching selectable in DB")
        print(f"{'=' * 60}")
        for entry in not_found:
            print(f"  Row {entry['row']}: codes={entry['codes']}  "
                  f"subcategory={entry['subcategory']}  {entry['description'][:60]}")


async def main():
    try:
        await update_subcategories()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
