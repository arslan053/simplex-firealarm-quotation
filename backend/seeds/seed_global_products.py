"""Seed script: load global products catalog from products.xlsx into products table."""

import argparse
import asyncio
import difflib
import os
import re
import sys
from decimal import Decimal, InvalidOperation

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.database import async_session_factory, engine

# ---------------------------------------------------------------------------
# Category normalization
# ---------------------------------------------------------------------------

CATEGORY_ENUM_VALUES = [
    "MX Devices",
    "Idnet Devices",
    "IDNAC",
    "Audio Panel",
    "Special Items",
    "conventional",
    "PC-TSW",
    "mimic panel",
    "Panel",
    "Remote Annunciator",
    "Repeator",
]

# Raw Excel value (lowercased, stripped) → enum target
_RAW_TO_ENUM: dict[str, str] = {
    "mx catageroy": "MX Devices",
    "mx category": "MX Devices",
    "idnet catageroy": "Idnet Devices",
    "idnet category": "Idnet Devices",
    "addressable notification": "IDNAC",
    "audio panel": "Audio Panel",
    "back boxes": "Special Items",
    "clock system": "Special Items",
    "special items": "Special Items",
    "enclosures": "Special Items",
    "remote led": "Special Items",
    "telephone fft": "Special Items",
    "fire supression": "Special Items",
    "conventional": "conventional",
    "conventional devices": "conventional",
    "conventional notification": "conventional",
    "graphics": "PC-TSW",
    "mimic panel": "mimic panel",
    "panel items": "Panel",
    "panel": "Panel",
    "remote annunciator": "Remote Annunciator",
    "repeator": "Repeator",
}

# Pre-compute lowercase enum values for fuzzy matching
_ENUM_LOWER = {v.lower(): v for v in CATEGORY_ENUM_VALUES}
_RAW_KEYS = list(_RAW_TO_ENUM.keys())


def normalize_category(raw: str) -> tuple[str, bool]:
    """Return (enum_value, warned). warned=True if fuzzy/fallback was used."""
    # Step 1: clean
    cleaned = raw.strip().strip("'\"").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    key = cleaned.lower()

    # Step 2: direct lookup
    if key in _RAW_TO_ENUM:
        return _RAW_TO_ENUM[key], False

    # Step 3: fuzzy match against known raw keys
    matches = difflib.get_close_matches(key, _RAW_KEYS, n=1, cutoff=0.75)
    if matches:
        return _RAW_TO_ENUM[matches[0]], True

    # Step 4: fallback
    return "Special Items", True


# ---------------------------------------------------------------------------
# Price parsing
# ---------------------------------------------------------------------------

def parse_price(val) -> Decimal | None:
    """Parse a price value, stripping $ and commas. Returns None on failure."""
    if pd.isna(val):
        return None
    s = str(val).strip().replace("$", "").replace(",", "").strip()
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


# ---------------------------------------------------------------------------
# Column detection
# ---------------------------------------------------------------------------

def detect_columns(df: pd.DataFrame) -> dict[str, str]:
    """Map logical names to actual DataFrame column names using keyword matching."""
    mapping: dict[str, str] = {}
    for col in df.columns:
        lower = str(col).lower().strip()
        if "part" in lower and "code" in lower:
            mapping["code"] = col
        elif "material" in lower and "description" in lower:
            mapping["description"] = col
        elif "price" in lower or "fy25" in lower:
            mapping["price"] = col
        elif "category" in lower or "catageroy" in lower:
            mapping["category"] = col
    return mapping


# ---------------------------------------------------------------------------
# Main seed logic
# ---------------------------------------------------------------------------

async def seed_products(excel_path: str):
    print(f"Reading Excel: {excel_path}")
    df = pd.read_excel(excel_path, header=3, engine="openpyxl")
    print(f"  Rows in sheet: {len(df)}")

    col_map = detect_columns(df)
    required = ["code", "description", "category"]
    for key in required:
        if key not in col_map:
            print(f"ERROR: Could not detect column for '{key}'. Found columns: {list(df.columns)}")
            sys.exit(1)

    print(f"  Column mapping: {col_map}")

    inserted = 0
    updated = 0
    skipped = 0
    warnings: list[str] = []

    async with async_session_factory() as db:
        for idx, row in df.iterrows():
            raw_code = row.get(col_map["code"])
            raw_desc = row.get(col_map["description"])
            raw_cat = row.get(col_map["category"])
            raw_price = row.get(col_map.get("price", ""), None) if "price" in col_map else None

            # Skip rows with missing required fields
            if pd.isna(raw_code) or pd.isna(raw_desc) or pd.isna(raw_cat):
                skipped += 1
                continue

            code = str(raw_code).strip()
            description = str(raw_desc).strip()
            if not code or not description:
                skipped += 1
                continue

            category, warned = normalize_category(str(raw_cat))
            if warned:
                msg = f"Row {idx}: category '{raw_cat}' → '{category}' (fuzzy/fallback)"
                warnings.append(msg)

            price = parse_price(raw_price)

            result = await db.execute(
                text("""
                    INSERT INTO products (code, description, price, currency, category)
                    VALUES (:code, :description, :price, 'USD', :category)
                    ON CONFLICT (code) DO UPDATE SET
                        description = EXCLUDED.description,
                        price       = EXCLUDED.price,
                        category    = EXCLUDED.category,
                        updated_at  = now()
                    RETURNING (xmax = 0) AS is_insert
                """),
                {"code": code, "description": description, "price": price, "category": category},
            )
            is_insert = result.scalar()
            if is_insert:
                inserted += 1
            else:
                updated += 1

        await db.commit()

    total = inserted + updated + skipped
    print(f"\n--- Summary ---")
    print(f"  Total rows processed: {total}")
    print(f"  Inserted: {inserted}")
    print(f"  Updated:  {updated}")
    print(f"  Skipped:  {skipped}")
    print(f"  Warnings: {len(warnings)}")
    for w in warnings:
        print(f"    {w}")


async def main():
    parser = argparse.ArgumentParser(description="Seed products from products.xlsx")
    parser.add_argument(
        "excel_path",
        nargs="?",
        default=os.path.join(os.path.dirname(__file__), "..", "..", "products.xlsx"),
        help="Path to products.xlsx (default: ../../products.xlsx relative to this script)",
    )
    args = parser.parse_args()

    try:
        await seed_products(args.excel_path)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
