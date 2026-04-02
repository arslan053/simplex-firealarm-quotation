"""Seed script: inserts Panel Selection prompt questions into the database."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, engine
from app.modules.prompt_questions.models import PromptQuestion

PANEL_QUESTIONS = [
    {
        "question_no": 101,
        "question": "Is this BOQ is for Multiple-Building Projects with each building having independent System with its own Panel?",
        "category": "Panel_selection",
    },
    {
        "question_no": 102,
        "question": "Is this BOQ Calls for Multiple Panels in Single Building like a high-rise tower having multiple Panels at different levels?",
        "category": "Panel_selection",
    },
    {
        "question_no": 103,
        "question": "Does BOQ represent a project where whole Project is having just one Single Panel in a Single Building?",
        "category": "Panel_selection",
    },
]


async def seed_panel_questions():
    async with async_session_factory() as db:
        # Check if already seeded
        result = await db.execute(
            select(PromptQuestion).where(
                PromptQuestion.category == "Panel_selection"
            )
        )
        if result.scalars().first():
            print("Panel selection questions already seeded. Skipping.")
            return

        for q in PANEL_QUESTIONS:
            db.add(PromptQuestion(**q))

        await db.commit()
        print("Panel selection questions seeded successfully!")
        for q in PANEL_QUESTIONS:
            print(f"  Q{q['question_no']}: {q['question'][:70]}...")


async def main():
    try:
        await seed_panel_questions()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
