"""Seed script: inserts prompt questions (Protocol_decision) into the database."""

import asyncio
import sys
import os

# Ensure the backend directory is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, engine
from app.modules.prompt_questions.models import PromptQuestion

PROMPT_QUESTIONS = [
    {
        "question_no": 1,
        "question": "Does Specs and / or BOQ calls for Short-Circuit isolator in each detector ?",
        "category": "Protocol_decision",
    },
    {
        "question_no": 2,
        "question": "Does Specs and / or BOQ calls for soft-addressable or Auto Addressing or device position based addressing in the System ?",
        "category": "Protocol_decision",
    },
    {
        "question_no": 3,
        "question": "Does Specs and / or BOQ calls for Loop Powered Sounder with no separate Power for Sounders?",
        "category": "Protocol_decision",
    },
    {
        "question_no": 4,
        "question": "Does Specs and / or BOQ calls for all Detection and notification devices on same Loop?",
        "category": "Protocol_decision",
    },
]


async def seed_prompt_questions():
    async with async_session_factory() as db:
        # Check if already seeded
        result = await db.execute(
            select(PromptQuestion).where(PromptQuestion.question_no == 1)
        )
        if result.scalar_one_or_none():
            print("Prompt questions already seeded. Skipping.")
            return

        for q in PROMPT_QUESTIONS:
            db.add(PromptQuestion(**q))

        await db.commit()
        print("Prompt questions seeded successfully!")
        for q in PROMPT_QUESTIONS:
            print(f"  Q{q['question_no']}: {q['question'][:60]}...")


async def main():
    try:
        await seed_prompt_questions()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
