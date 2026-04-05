"""Seed script: load 4007 panel selection questions into prompt_questions."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.database import async_session_factory, engine
from app.modules.prompt_questions.models import PromptQuestion

CATEGORY = "4007_panel_questions"

QUESTIONS = [
    {
        "question_no": 2,
        "question": (
            "Does the BOQ require speakers, amplifiers, or audio notification devices?"
        ),
    },
    {
        "question_no": 3,
        "question": (
            "Does the BOQ require telephone jacks, FFT (Firefighter Telephone), "
            "or fire warden intercom?"
        ),
    },
    {
        "question_no": 14,
        "question": "Does the BOQ mention a printer or require printing capability?",
    },
    {
        "question_no": 18,
        "question": (
            "Does the BOQ mention a graphic annunciator, mimic panel, "
            "or mimic display? (Note: a 'graphic station' or 'FAS graphic "
            "station' is a workstation/PC — NOT a graphic annunciator. "
            "Do not match it.)"
        ),
    },
    {
        "question_no": 20,
        "question": (
            "Does the BOQ mention a panel-mounted annunciator, built-in annunciator, "
            "or door-mounted annunciator?"
        ),
    },
]


async def seed():
    async with async_session_factory() as db:
        # Check if already seeded
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


async def add_missing():
    """Insert only questions whose question_no doesn't already exist."""
    async with async_session_factory() as db:
        existing = await db.execute(
            select(PromptQuestion.question_no).where(
                PromptQuestion.category == CATEGORY
            )
        )
        existing_nos = {row[0] for row in existing.fetchall()}

        added = 0
        for q in QUESTIONS:
            if q["question_no"] not in existing_nos:
                db.add(PromptQuestion(
                    question_no=q["question_no"],
                    question=q["question"],
                    category=CATEGORY,
                ))
                added += 1
                print(f"  Adding Q{q['question_no']}")

        if added:
            await db.commit()
            print(f"Added {added} missing question(s).")
        else:
            print("All questions already exist — nothing to add.")


async def main():
    try:
        await seed()
        await add_missing()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
