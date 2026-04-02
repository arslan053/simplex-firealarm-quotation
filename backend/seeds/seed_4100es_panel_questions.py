"""Seed script: load 4100ES panel selection questions into prompt_questions."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.database import async_session_factory, engine
from app.modules.prompt_questions.models import PromptQuestion

CATEGORY = "4100ES_panel_questions"

QUESTIONS = [
    {
        "question_no": 201,
        "question": (
            "Do the specifications call for a touchscreen display, "
            "multi-line display, or bilingual/2-language support for the panel?"
        ),
    },
    {
        "question_no": 202,
        "question": (
            "Do the specifications call for backup or redundant amplifiers?"
        ),
    },
    {
        "question_no": 203,
        "question": (
            "Do the specifications call for Class A wiring for speakers "
            "or telephone circuits?"
        ),
    },
    {
        "question_no": 204,
        "question": (
            "Does the BOQ or specification require BMS (Building Management System) "
            "integration or BACnet connectivity?"
        ),
    },
    {
        "question_no": 206,
        "question": (
            "What is the total telephone jack count from the BOQ? "
            "Count all firefighter telephone jacks, FFT jacks, and phone stations. "
            "Return the numeric total (0 if none)."
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


async def main():
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
