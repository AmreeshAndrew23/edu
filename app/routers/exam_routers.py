from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import APIRouter, Depends, HTTPException

from app.core.database import get_db
from app.models.exam import Exam
from app.models.exam_blueprint import ExamBlueprint
from app.models.subject import Subject
from app.models.topic import Topic
from app.schemas.exam_schema import ExamResponse, SubjectInExamResponse, TopicInExamResponse

router = APIRouter(prefix="/exams", tags=["Exams"])


@router.get("/", response_model=list[ExamResponse])
async def list_exams(db: AsyncSession = Depends(get_db)):
    """List all available exams (NEET 2025, NEET 2026, etc.)."""
    import logging
    log = logging.getLogger(__name__)
    result = await db.execute(select(Exam).order_by(Exam.exam_year.desc(), Exam.exam_name))
    exams = result.scalars().all()
    log.info(f"GET /exams → Returning {len(exams)} exams:")
    for e in exams[:8]:  # Log first 8
        log.info(f"  - id={e.id}, {e.exam_name} {e.exam_year}, desc={e.description[:60]}")
    return exams


@router.get("/{exam_id}/subjects", response_model=list[SubjectInExamResponse])
async def get_subjects_in_exam(exam_id: int, db: AsyncSession = Depends(get_db)):
    """
    Return distinct subjects that have blueprint entries for this exam.
    e.g., NEET 2026 → [Physics, Chemistry, Biology]
    """
    import logging
    log = logging.getLogger(__name__)

    exam = await db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    log.info(f"GET /exams/{exam_id}/subjects → Exam: {exam.exam_name} {exam.exam_year} (subject_id={exam.subject_id})")

    # Check blueprints for this exam
    from sqlalchemy import func
    bp_count = (await db.execute(
        select(func.count(ExamBlueprint.id)).where(ExamBlueprint.exam_id == exam_id)
    )).scalar()
    log.info(f"  → Total blueprints for this exam: {bp_count}")

    result = await db.execute(
        select(Subject)
        .join(Topic, Topic.subject_id == Subject.id)
        .join(ExamBlueprint, ExamBlueprint.topic_id == Topic.id)
        .where(ExamBlueprint.exam_id == exam_id)
        .distinct()
        .order_by(Subject.name)
    )
    subjects = result.scalars().all()
    log.info(f"  → Subjects found: {[s.name for s in subjects]}")

    if not subjects:
        raise HTTPException(status_code=404, detail="No subjects found for this exam")

    return subjects


@router.get("/{exam_id}/subjects/{subject_id}/topics", response_model=list[TopicInExamResponse])
async def get_topics_in_exam_subject(
    exam_id: int,
    subject_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Return topics (with blueprint metadata) for a given exam + subject.
    e.g., NEET 2026 + Physics → [Thermodynamics (5 Qs, hard), Optics (4 Qs, medium), ...]
    """
    exam = await db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    subject = await db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    result = await db.execute(
        select(
            Topic.id,
            Topic.topic_name,
            ExamBlueprint.expected_questions,
            ExamBlueprint.difficulty_level,
        )
        .join(ExamBlueprint, ExamBlueprint.topic_id == Topic.id)
        .where(
            ExamBlueprint.exam_id == exam_id,
            Topic.subject_id == subject_id,
        )
        .order_by(Topic.topic_name)
    )
    rows = result.all()

    if not rows:
        raise HTTPException(status_code=404, detail="No topics found for this exam and subject")

    return [
        TopicInExamResponse(
            id=row.id,
            topic_name=row.topic_name,
            expected_questions=row.expected_questions,
            difficulty_level=row.difficulty_level,
        )
        for row in rows
    ]
