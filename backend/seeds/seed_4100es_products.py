"""Seed script: insert 4100ES-specific products missing from the catalog."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.database import async_session_factory, engine

PRODUCTS = [
    {
        "code": "4100-1461",
        "description": "8-Switch and 8-LED Module",
        "category": "Panel",
    },
    {
        "code": "4100-1450",
        "description": "LED Controller",
        "category": "Panel",
    },
    {
        "code": "4100-1273",
        "description": "Phone Class A NAC Adapter",
        "category": "Panel",
    },
]


async def seed():
    async with async_session_factory() as db:
        inserted = 0
        updated = 0

        for p in PRODUCTS:
            result = await db.execute(
                text("""
                    INSERT INTO products (code, description, category)
                    VALUES (:code, :description, :category)
                    ON CONFLICT (code) DO UPDATE SET
                        description = EXCLUDED.description,
                        category    = EXCLUDED.category,
                        updated_at  = now()
                    RETURNING (xmax = 0) AS is_insert
                """),
                p,
            )
            if result.scalar():
                inserted += 1
            else:
                updated += 1

        await db.commit()
        print(f"4100ES products: {inserted} inserted, {updated} updated.")


async def main():
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
