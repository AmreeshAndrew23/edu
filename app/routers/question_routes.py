from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict

from app.core.database import get_db
from app.models.question import Question
from app.models.subject import Subject
from app.models.topic import Topic
from app.models.exam import Exam

router = APIRouter(prefix="/questions", tags=["Questions"])

_SUBJECT_KEY_TO_NAME = {
    'physics':   'Physics',
    'chemistry': 'Chemistry',
    'biology':   'Biology',
}
_CORE_SUBJECTS = ['Physics', 'Chemistry', 'Biology']
_FULL_SUBJECT  = 'All Subjects'


class QuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exam_id: int
    topic_id: int
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    difficulty_level: str | None


class QuestionUploadItem(BaseModel):
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str           # 'A' | 'B' | 'C' | 'D'
    explanation: str | None = None
    topic_name: str
    difficulty: str = 'medium'


class QuestionUploadRequest(BaseModel):
    subject: Literal['physics', 'chemistry', 'biology', 'full_neet']
    year: int
    questions: list[QuestionUploadItem]


class UploadResult(BaseModel):
    uploaded: int
    skipped: int
    created_topics: list[str]


@router.get("/", response_model=list[QuestionResponse])
async def list_questions(
    exam_id: int | None = None,
    topic_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Question)
    if exam_id:
        query = query.where(Question.exam_id == exam_id)
    if topic_id:
        query = query.where(Question.topic_id == topic_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/upload", response_model=UploadResult)
async def upload_questions(payload: QuestionUploadRequest, db: AsyncSession = Depends(get_db)):
    """
    Bulk-upload NEET previous-year questions.

    - subject: physics | chemistry | biology | full_neet
    - year: the NEET paper year (e.g. 2020)
    - questions: array of MCQ objects with topic_name

    For single subjects, unknown topics are auto-created.
    For full_neet, topic_name must match an existing topic (search across all 3 subjects).
    Duplicate question_text + topic_id combos are skipped.
    """
    is_full = payload.subject == 'full_neet'

    # ── Resolve exam and subject(s) ──────────────────────────────────────────

    if is_full:
        full_sub = (await db.execute(
            select(Subject).where(Subject.name == _FULL_SUBJECT)
        )).scalar_one_or_none()
        if not full_sub:
            raise HTTPException(400, "Full-exam subject row not found — ensure the seed has run.")

        exam = (await db.execute(
            select(Exam)
            .where(Exam.subject_id == full_sub.id)
            .order_by(Exam.exam_year.desc())
        )).scalars().first()

        # Pre-load topics from all 3 core subjects
        core_sub_rows = (await db.execute(
            select(Subject).where(Subject.name.in_(_CORE_SUBJECTS))
        )).scalars().all()
        core_sub_ids = [s.id for s in core_sub_rows]
        topics_rows = (await db.execute(
            select(Topic).where(Topic.subject_id.in_(core_sub_ids))
        )).scalars().all()
        topic_map = {t.topic_name.lower(): t for t in topics_rows}
        single_subject = None

    else:
        subject_name = _SUBJECT_KEY_TO_NAME[payload.subject]
        sub = (await db.execute(
            select(Subject).where(Subject.name == subject_name)
        )).scalar_one_or_none()
        if not sub:
            raise HTTPException(400, f"Subject '{subject_name}' not found — ensure the seed has run.")

        exam = (await db.execute(
            select(Exam)
            .where(Exam.subject_id == sub.id)
            .order_by(Exam.exam_year.desc())
        )).scalars().first()

        topics_rows = (await db.execute(
            select(Topic).where(Topic.subject_id == sub.id)
        )).scalars().all()
        topic_map = {t.topic_name.lower(): t for t in topics_rows}
        single_subject = sub

    if not exam:
        raise HTTPException(400, "No exam found for this subject — ensure the seed has run.")

    # ── Insert questions ──────────────────────────────────────────────────────

    uploaded = 0
    skipped  = 0
    created_topics: list[str] = []

    for q in payload.questions:
        topic = topic_map.get(q.topic_name.strip().lower())

        if not topic:
            if is_full:
                # Can't infer subject for unknown topic in full_neet mode
                skipped += 1
                continue
            # Auto-create topic under the single subject
            topic = Topic(topic_name=q.topic_name.strip(), subject_id=single_subject.id)
            db.add(topic)
            await db.flush()
            topic_map[q.topic_name.strip().lower()] = topic
            created_topics.append(q.topic_name.strip())

        # Duplicate check (same text + topic)
        exists = (await db.execute(
            select(Question.id).where(
                Question.question_text == q.question_text,
                Question.topic_id == topic.id,
            )
        )).scalar_one_or_none()

        if exists:
            skipped += 1
            continue

        db.add(Question(
            exam_id=exam.id,
            topic_id=topic.id,
            question_text=q.question_text,
            option_a=q.option_a,
            option_b=q.option_b,
            option_c=q.option_c,
            option_d=q.option_d,
            correct_option=q.correct_option.upper(),
            explanation=q.explanation,
            difficulty_level=q.difficulty,
            source='neet_paper',
            neet_year=payload.year,
        ))
        uploaded += 1

    await db.commit()
    return UploadResult(uploaded=uploaded, skipped=skipped, created_topics=created_topics)
