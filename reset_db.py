#!/usr/bin/env python
"""Reset database and seed from scratch."""
import asyncio
import logging
import sys
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def reset_and_seed():
    from app.core.database import AsyncSessionLocal, engine, Base
    from app.models import (
        Country, State, Student, Subject, Topic,
        Exam, ExamBlueprint, Question, ExamSession, StudentAnswer, ChatLog, AiUsageLog,
    )
    from app.seed.seed_all import seed_all

    try:
        # Drop all tables
        logger.info("Dropping all tables...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("✓ Tables dropped")

        # Create all tables
        logger.info("Creating all tables...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✓ Tables created")

        # Run migrations
        _migrations = [
            "ALTER TABLE students ADD COLUMN IF NOT EXISTS first_name VARCHAR(50)",
            "ALTER TABLE students ADD COLUMN IF NOT EXISTS last_name VARCHAR(50)",
            "ALTER TABLE students ADD COLUMN IF NOT EXISTS phone VARCHAR(25)",
            "ALTER TABLE students ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)",
            "ALTER TABLE students ALTER COLUMN name DROP NOT NULL",
            "ALTER TABLE questions ADD COLUMN IF NOT EXISTS source VARCHAR(20) NOT NULL DEFAULT 'ai_generated'",
            "ALTER TABLE questions ADD COLUMN IF NOT EXISTS neet_year INTEGER",
            "ALTER TABLE questions ADD COLUMN IF NOT EXISTS paper_order INTEGER",
        ]
        logger.info("Running migrations...")
        for _sql in _migrations:
            try:
                async with engine.begin() as conn:
                    await conn.execute(text(_sql))
            except Exception as exc:
                logger.warning(f"Migration skipped: {_sql[:60]} — {exc}")
        logger.info("✓ Migrations complete")

        # Seed data
        logger.info("Seeding database...")
        async with AsyncSessionLocal() as db:
            await seed_all(db)
        logger.info("✓ Database seeded")

        # Verify
        logger.info("Verifying...")
        async with AsyncSessionLocal() as db:
            from sqlalchemy import func, select
            from app.models.exam import Exam
            from app.models.exam_blueprint import ExamBlueprint
            from app.models.subject import Subject
            from app.models.topic import Topic

            exams = (await db.execute(select(func.count()).select_from(Exam))).scalar()
            bps = (await db.execute(select(func.count()).select_from(ExamBlueprint))).scalar()

            # Get subjects with blueprint counts
            subject_bp_counts = (await db.execute(
                select(Subject.name, func.count(ExamBlueprint.id).label("bp_count"))
                .outerjoin(ExamBlueprint)
                .group_by(Subject.name)
            )).all()

            logger.info(f"✓ Total exams: {exams}")
            logger.info(f"✓ Total blueprints: {bps}")
            logger.info(f"✓ Blueprints by subject:")
            for name, count in subject_bp_counts:
                if name != "All Subjects":
                    logger.info(f"  - {name}: {count}")

            # Check Full Exam specifically
            full_exam = (await db.execute(
                select(Exam).where(Exam.exam_name == "NEET")
                .where(Exam.exam_year == 2026)
                .join(Subject, Subject.id == Exam.subject_id)
                .where(Subject.name == "All Subjects")
            )).scalar_one_or_none()

            if full_exam:
                full_bps = (await db.execute(
                    select(func.count(ExamBlueprint.id))
                    .where(ExamBlueprint.exam_id == full_exam.id)
                )).scalar()
                logger.info(f"✓ Full NEET 2026 exam (id={full_exam.id}) has {full_bps} blueprints")

                # Check per subject in full exam
                full_exam_subjects = (await db.execute(
                    select(Subject.name, func.count(ExamBlueprint.id).label("bp_count"))
                    .join(Topic, Topic.subject_id == Subject.id)
                    .join(ExamBlueprint, ExamBlueprint.topic_id == Topic.id)
                    .where(ExamBlueprint.exam_id == full_exam.id)
                    .group_by(Subject.name)
                )).all()
                logger.info(f"  Subjects in Full NEET exam:")
                for name, count in full_exam_subjects:
                    logger.info(f"    - {name}: {count} blueprints")

        logger.info("=" * 60)
        logger.info("RESET AND SEED COMPLETE")
        logger.info("=" * 60)
        return True

    except Exception as exc:
        logger.error(f"FAILED: {exc}", exc_info=True)
        return False


if __name__ == "__main__":
    result = asyncio.run(reset_and_seed())
    sys.exit(0 if result else 1)
