import random

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, ConfigDict

from app.core.database import get_db
from app.models.student_answer import StudentAnswer
from app.models.question import Question
from app.models.topic import Topic
from app.models.exam_session import ExamSession
from app.schemas.session_schema import (
    SessionStartRequest,
    SessionStartResponse,
    SubmitAnswersRequest,
    SessionResultResponse,
)
from app.services.session_service import start_session, submit_session, get_session_results

router = APIRouter(prefix="/sessions", tags=["Exam Sessions"])


class WeakTopic(BaseModel):
    topic_id: int
    topic_name: str
    total: int
    wrong: int
    accuracy: float  # 0–100


class RecallQuestion(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str
    explanation: str | None
    topic_name: str


@router.get("/weak-topics", response_model=list[WeakTopic])
async def get_weak_topics(
    student_id: int,
    exam_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Return topics ranked by lowest accuracy for this student on this exam.
    Only topics with at least 3 attempted questions are included.
    """
    rows = (await db.execute(
        select(
            Question.topic_id,
            Topic.topic_name,
            func.count(StudentAnswer.id).label("total"),
            func.sum(
                func.cast(StudentAnswer.is_correct == False, func.Integer())  # noqa: E712
            ).label("wrong"),
        )
        .join(StudentAnswer, StudentAnswer.question_id == Question.id)
        .join(ExamSession, ExamSession.id == StudentAnswer.session_id)
        .join(Topic, Topic.id == Question.topic_id)
        .where(
            ExamSession.student_id == student_id,
            ExamSession.exam_id == exam_id,
            ExamSession.status == "completed",
        )
        .group_by(Question.topic_id, Topic.topic_name)
        .having(func.count(StudentAnswer.id) >= 3)
        .order_by(func.sum(
            func.cast(StudentAnswer.is_correct == False, func.Integer())  # noqa: E712
        ).desc())
    )).all()

    return [
        WeakTopic(
            topic_id=r.topic_id,
            topic_name=r.topic_name,
            total=r.total,
            wrong=r.wrong,
            accuracy=round((1 - r.wrong / r.total) * 100, 1),
        )
        for r in rows
    ]


@router.get("/count")
async def get_session_count(student_id: int, db: AsyncSession = Depends(get_db)):
    """Total completed quiz sessions for a student (used to gate Weak Area Detection)."""
    count = (await db.execute(
        select(func.count())
        .select_from(ExamSession)
        .where(ExamSession.student_id == student_id)
        .where(ExamSession.status == "completed")
    )).scalar()
    return {"count": count or 0}


@router.get("/recall-questions", response_model=list[RecallQuestion])
async def get_recall_questions(
    student_id: int,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """
    Returns a shuffled mix of:
    1. Questions the student has previously answered (session history)
    2. NEET previous-year questions uploaded into the DB (source='neet_paper')

    Deduplicates by question id before shuffling.
    """
    _cols = (
        Question.id, Question.question_text,
        Question.option_a, Question.option_b, Question.option_c, Question.option_d,
        Question.correct_option, Question.explanation, Topic.topic_name,
    )

    # 1. Student's session history
    session_rows = (await db.execute(
        select(*_cols)
        .join(StudentAnswer, StudentAnswer.question_id == Question.id)
        .join(ExamSession, ExamSession.id == StudentAnswer.session_id)
        .join(Topic, Topic.id == Question.topic_id)
        .where(
            ExamSession.student_id == student_id,
            ExamSession.status == "completed",
        )
        .distinct()
    )).all()

    # 2. NEET previous-year paper questions
    neet_rows = (await db.execute(
        select(*_cols)
        .join(Topic, Topic.id == Question.topic_id)
        .where(Question.source == 'neet_paper')
    )).all()

    # Merge, deduplicate by id, shuffle, limit
    seen: set[int] = set()
    combined = []
    for r in session_rows + neet_rows:
        if r.id not in seen:
            seen.add(r.id)
            combined.append(r)

    random.shuffle(combined)

    return [
        RecallQuestion(
            id=r.id,
            question_text=r.question_text,
            option_a=r.option_a,
            option_b=r.option_b,
            option_c=r.option_c,
            option_d=r.option_d,
            correct_option=r.correct_option,
            explanation=r.explanation,
            topic_name=r.topic_name,
        )
        for r in combined[:limit]
    ]


@router.post("/start", response_model=SessionStartResponse)
async def start_exam_session(
    payload: SessionStartRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Start a model exam session.

    Selection rules (blueprint-driven):
    - exam_id only               → full exam (all subjects + all topics)
    - exam_id + subject_id       → one subject, all its topics in that exam
    - exam_id + subject_id + topic_id → single topic only

    Returns session_id + question list (correct options hidden).
    """
    return await start_session(db, payload)


@router.post("/{session_id}/submit", response_model=SessionResultResponse)
async def submit_exam_session(
    session_id: int,
    payload: SubmitAnswersRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit answers for a session. Returns score + per-question breakdown
    with correct options and explanations revealed.
    """
    return await submit_session(db, session_id, payload)


@router.get("/{session_id}/results", response_model=SessionResultResponse)
async def get_exam_results(
    session_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve results for an already-submitted session."""
    return await get_session_results(db, session_id)
