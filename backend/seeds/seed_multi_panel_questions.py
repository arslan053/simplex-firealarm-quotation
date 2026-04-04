"""Seed script: multi-panel loop detection questions into prompt_questions."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.database import async_session_factory, engine
from app.modules.prompt_questions.models import PromptQuestion

CATEGORY = "multi_panel_questions"

QUESTIONS = [
    {
        "question_no": 21,
        "question": (
            "For each BOQ item that describes a fire alarm control panel, "
            "extract the number of SLC (Signaling Line Circuit) loops mentioned. "
            "Look for patterns like '1-loop', '2-loop panel', 'single loop', "
            "'dual loop', 'two loops', 'four loop', 'quad loop', 'twelve loop', "
            "'loop card', 'SLC loop', etc. "
            "Convert word-based numbers to integers (e.g. 'two'→2, 'dual'→2, "
            "'single'→1, 'triple'→3, 'quad'→4, 'twelve'→12). "
            "Return your answer as a JSON array string with one object per "
            "matching BOQ item. Each object must have exactly two keys: "
            '"boq_item_id" (the item\'s "id" copied verbatim from the BOQ) '
            'and "loop_count" (integer). '
            'Example: [{"boq_item_id": "abc-123", "loop_count": 2}]. '
            "If NO items mention loops, return []. "
            "Only extract what is explicitly stated — do NOT guess or infer."
        ),
    },
]


async def seed():
    async with async_session_factory() as db:
        existing = await db.execute(
            select(PromptQuestion).where(PromptQuestion.category == CATEGORY)
        )
        if existing.scalars().first():
            print(f"Questions with category '{CATEGORY}' already exist — skipping.")
            return

        for q in QUESTIONS:
            db.add(PromptQuestion(
                question_no=q["question_no"],
                question=q["question"],
                category=CATEGORY,
            ))

        await db.commit()
        print(f"Seeded {len(QUESTIONS)} questions with category '{CATEGORY}'.")


async def migrate_q21():
    """Migrate Q21 from 4007_panel_questions to multi_panel_questions.

    Updates category and question text if Q21 exists under old category.
    """
    q21_text = next(
        q["question"] for q in QUESTIONS if q["question_no"] == 21
    )
    async with async_session_factory() as db:
        result = await db.execute(
            select(PromptQuestion).where(
                PromptQuestion.question_no == 21,
                PromptQuestion.category == "4007_panel_questions",
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            print("Q21 not found under 4007_panel_questions — nothing to migrate.")
            return
        row.category = CATEGORY
        row.question = q21_text
        await db.commit()
        print("Migrated Q21: 4007_panel_questions → multi_panel_questions.")


async def main():
    try:
        await migrate_q21()
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
