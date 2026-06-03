import random

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from pydantic import BaseModel, ConfigDict

from app.core.database import get_db
from app.models.student_answer import StudentAnswer
from app.models.question import Question
from app.models.topic import Topic
from app.models.subject import Subject
from app.models.exam_session import ExamSession
from app.models.exam import Exam
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
            func.sum(case((StudentAnswer.is_correct == False, 1), else_=0)).label("wrong"),  # noqa: E712
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
        .order_by(func.sum(case((StudentAnswer.is_correct == False, 1), else_=0)).desc())  # noqa: E712
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
    Returns questions the student has previously answered, shuffled for spaced repetition.
    Only uses the student's own session history — no new questions are introduced.
    """
    _cols = (
        Question.id, Question.question_text,
        Question.option_a, Question.option_b, Question.option_c, Question.option_d,
        Question.correct_option, Question.explanation, Topic.topic_name,
    )

    rows = (await db.execute(
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

    random.shuffle(rows)

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
        for r in rows[:limit]
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


# ── Rapid Revision (NEET previous-year papers) ────────────────────────────────

@router.get("/neet-years")
async def get_neet_years(db: AsyncSession = Depends(get_db)):
    """Returns distinct years available from uploaded NEET paper questions."""
    years = (await db.execute(
        select(Question.neet_year)
        .where(Question.source == "neet_paper", Question.neet_year.isnot(None))
        .distinct()
        .order_by(Question.neet_year.desc())
    )).scalars().all()
    return {"years": list(years)}


class RapidRevisionRequest(BaseModel):
    student_id: int
    year: int | None = None
    subject_id: int | None = None


@router.post("/rapid-revision", response_model=SessionStartResponse)
async def start_rapid_revision(
    payload: RapidRevisionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Start a model exam session using uploaded NEET previous-year paper questions.
    Optionally filter by year and/or subject.
    """
    exam = (await db.execute(select(Exam).limit(1))).scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=404, detail="No exam found in database.")

    q_filters = [Question.source == "neet_paper"]
    if payload.year:
        q_filters.append(Question.neet_year == payload.year)
    if payload.subject_id:
        q_filters.append(
            Question.topic_id.in_(
                select(Topic.id).where(Topic.subject_id == payload.subject_id)
            )
        )

    questions = (await db.execute(
        select(Question).where(*q_filters).order_by(func.random())
    )).scalars().all()

    if not questions:
        year_label = f" for NEET {payload.year}" if payload.year else ""
        raise HTTPException(
            status_code=404,
            detail=f"No NEET paper questions found{year_label}. Upload questions via POST /questions/upload first.",
        )

    session = ExamSession(
        student_id=payload.student_id,
        exam_id=exam.id,
        status="in_progress",
        total_questions=len(questions),
        started_at=datetime.utcnow(),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return SessionStartResponse(
        session_id=session.id,
        total_questions=session.total_questions,
        exam_id=session.exam_id,
        difficulty="neet_paper",
        questions=[QuestionPayload.model_validate(q) for q in questions],
    )
