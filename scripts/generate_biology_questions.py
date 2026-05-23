"""
Batch question generator for all Biology topics in a given exam year.
Reads blueprints to know how many questions to generate per topic.
Skips topics that already have enough questions.

Usage:
    venv/Scripts/python.exe -m scripts.generate_biology_questions --year 2026
"""

import asyncio
import argparse
from sqlalchemy import select, func
from app.core.database import AsyncSessionLocal
from app.models.subject import Subject
from app.models.exam import Exam
from app.models.topic import Topic
from app.models.exam_blueprint import ExamBlueprint
from app.models.question import Question
from app.services.question_service import generate_questions


async def run(year: int) -> None:
    async with AsyncSessionLocal() as db:
        # Resolve Biology subject
        bio = (await db.execute(
            select(Subject).where(Subject.name == "Biology")
        )).scalar_one_or_none()
        if not bio:
            print("Biology subject not found. Run the server once to seed.")
            return

        # Resolve the per-subject Biology exam for this year
        exam = (await db.execute(
            select(Exam).where(
                Exam.exam_name == "NEET",
                Exam.exam_year == year,
                Exam.subject_id == bio.id,
            )
        )).scalar_one_or_none()
        if not exam:
            print(f"NEET {year} Biology exam not found. Run the server once to seed.")
            return

        print(f"Generating questions for: {exam.exam_name} {exam.exam_year} — Biology (exam_id={exam.id})")
        print("=" * 60)

        # Get all blueprints for this exam that belong to Biology topics
        blueprints = (await db.execute(
            select(ExamBlueprint, Topic)
            .join(Topic, ExamBlueprint.topic_id == Topic.id)
            .where(
                ExamBlueprint.exam_id == exam.id,
                Topic.subject_id == bio.id,
            )
            .order_by(Topic.id)
        )).all()

        total_generated = 0
        total_skipped = 0

        for bp, topic in blueprints:
            # Count existing questions for this exam + topic
            existing = (await db.execute(
                select(func.count()).select_from(Question).where(
                    Question.exam_id == exam.id,
                    Question.topic_id == topic.id,
                )
            )).scalar()

            needed = bp.expected_questions - existing
            if needed <= 0:
                print(f"  SKIP  {topic.topic_name} ({existing}/{bp.expected_questions} already present)")
                total_skipped += 1
                continue

            print(f"  GEN   {topic.topic_name} — {needed} questions ({bp.difficulty_level})... ", end="", flush=True)

            try:
                generated = await generate_questions(
                    exam_name=exam.exam_name,
                    subject_name="Biology",
                    topic_name=topic.topic_name,
                    difficulty=bp.difficulty_level,
                    count=needed,
                )
            except Exception as e:
                print(f"ERROR: {e}")
                continue

            required = {"question_text", "option_a", "option_b", "option_c", "option_d", "correct_option"}
            for q in generated:
                if not required.issubset(q.keys()):
                    print(f"  WARNING: Skipping malformed question: {list(q.keys())}")
                    continue
                db.add(Question(
                    exam_id=exam.id,
                    topic_id=topic.id,
                    question_text=q["question_text"],
                    option_a=q["option_a"],
                    option_b=q["option_b"],
                    option_c=q["option_c"],
                    option_d=q["option_d"],
                    correct_option=q["correct_option"].upper(),
                    explanation=q.get("explanation"),
                    difficulty_level=bp.difficulty_level,
                ))

            await db.commit()
            print(f"saved {len(generated)}")
            total_generated += len(generated)

        print("=" * 60)
        print(f"Done. Generated: {total_generated} | Skipped: {total_skipped} topics")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2026)
    args = parser.parse_args()
    asyncio.run(run(args.year))
