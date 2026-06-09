import logging
from datetime import date, timedelta

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import case, cast, Date, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.exam_session import ExamSession
from app.models.parent import Parent
from app.models.question import Question
from app.models.student import Student
from app.models.student_answer import StudentAnswer
from app.models.subject import Subject
from app.models.topic import Topic

router = APIRouter(prefix="/parent", tags=["Parent"])
logger = logging.getLogger(__name__)


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _compute_streak(session_dates: set) -> int:
    if not session_dates:
        return 0
    today = date.today()
    start = today if today in session_dates else today - timedelta(days=1)
    streak, check = 0, start
    while check in session_dates:
        streak += 1
        check -= timedelta(days=1)
    return streak


# ── Schemas ───────────────────────────────────────────────────────────────────

class ParentRegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    phone: str | None = None


class ParentLoginRequest(BaseModel):
    email: str
    password: str


class ParentResponse(BaseModel):
    id: int
    name: str
    email: str
    phone: str | None = None


class LinkChildRequest(BaseModel):
    parent_id: int
    child_email: str


# ── Auth endpoints ────────────────────────────────────────────────────────────

@router.post("/auth/register", response_model=ParentResponse)
async def register_parent(payload: ParentRegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = (await db.execute(
        select(Parent).where(Parent.email == payload.email.lower())
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    parent = Parent(
        name=payload.name,
        email=payload.email.lower(),
        phone=payload.phone or None,
        password_hash=_hash(payload.password),
    )
    db.add(parent)
    await db.commit()
    await db.refresh(parent)
    return ParentResponse(id=parent.id, name=parent.name, email=parent.email, phone=parent.phone)


@router.post("/auth/login", response_model=ParentResponse)
async def login_parent(payload: ParentLoginRequest, db: AsyncSession = Depends(get_db)):
    parent = (await db.execute(
        select(Parent).where(Parent.email == payload.email.lower())
    )).scalar_one_or_none()

    if not parent or not _verify_password(payload.password, parent.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return ParentResponse(id=parent.id, name=parent.name, email=parent.email, phone=parent.phone)


# ── Child linking ─────────────────────────────────────────────────────────────

@router.post("/link-child")
async def link_child(payload: LinkChildRequest, db: AsyncSession = Depends(get_db)):
    parent = await db.get(Parent, payload.parent_id)
    if not parent:
        raise HTTPException(status_code=404, detail="Parent not found")

    student = (await db.execute(
        select(Student).where(Student.email == payload.child_email.lower())
    )).scalar_one_or_none()

    if not student:
        raise HTTPException(status_code=404, detail="No student found with that email address")

    if student.parent_id and student.parent_id != payload.parent_id:
        raise HTTPException(status_code=409, detail="This student is already linked to another parent")

    student.parent_id = payload.parent_id
    await db.commit()
    return {
        "message": f"{student.first_name} {student.last_name} linked successfully",
        "student_id": student.id,
        "student_name": f"{student.first_name} {student.last_name}",
    }


@router.delete("/unlink-child")
async def unlink_child(parent_id: int, student_id: int, db: AsyncSession = Depends(get_db)):
    student = await db.get(Student, student_id)
    if not student or student.parent_id != parent_id:
        raise HTTPException(status_code=404, detail="Child not linked to this parent")
    student.parent_id = None
    await db.commit()
    return {"message": "Child unlinked"}


# ── Children stats ────────────────────────────────────────────────────────────

@router.get("/children")
async def get_children(parent_id: int, db: AsyncSession = Depends(get_db)):
    """Return all children linked to this parent, each with summary performance stats."""

    students = (await db.execute(
        select(Student).where(Student.parent_id == parent_id)
    )).scalars().all()

    results = []
    for student in students:
        base_filter = [
            ExamSession.student_id == student.id,
            ExamSession.status == "completed",
            ExamSession.correct_count.isnot(None),
        ]

        total_sessions = (await db.execute(
            select(func.count()).select_from(ExamSession).where(*base_filter)
        )).scalar() or 0

        total_questions = (await db.execute(
            select(func.count()).select_from(StudentAnswer)
            .join(ExamSession, ExamSession.id == StudentAnswer.session_id)
            .where(*base_filter)
        )).scalar() or 0

        # Streak
        date_rows = (await db.execute(
            select(cast(ExamSession.completed_at, Date).label("d"))
            .where(*base_filter, ExamSession.completed_at.isnot(None))
            .distinct()
        )).all()
        session_dates = {r.d for r in date_rows if r.d is not None}
        streak = _compute_streak(session_dates)

        # NEET score estimate from last 50 answered questions
        last50_subq = (
            select(StudentAnswer.is_correct)
            .join(ExamSession, ExamSession.id == StudentAnswer.session_id)
            .where(*base_filter, StudentAnswer.selected_option.isnot(None))
            .order_by(StudentAnswer.id.desc())
            .limit(50)
            .subquery()
        )
        n50 = (await db.execute(
            select(
                func.sum(case((last50_subq.c.is_correct == True, 1), else_=0)).label("correct"),  # noqa: E712
                func.count().label("total"),
            ).select_from(last50_subq)
        )).one()

        n50_correct = n50.correct or 0
        n50_total   = n50.total   or 0
        n50_wrong   = n50_total - n50_correct
        neet_score  = 0
        if n50_total > 0:
            neet_score = max(0, min(720, round(
                (n50_correct * 4 - n50_wrong) / (n50_total * 4) * 720
            )))

        # Per-subject accuracy
        subj_rows = (await db.execute(
            select(
                Subject.name.label("subject"),
                func.count(StudentAnswer.id).label("total"),
                func.sum(case((StudentAnswer.is_correct == True, 1), else_=0)).label("correct"),  # noqa: E712
            )
            .join(ExamSession, ExamSession.id == StudentAnswer.session_id)
            .join(Question,    Question.id    == StudentAnswer.question_id)
            .join(Topic,       Topic.id       == Question.topic_id)
            .join(Subject,     Subject.id     == Topic.subject_id)
            .where(*base_filter, Subject.name.in_(["Physics", "Chemistry", "Biology"]))
            .group_by(Subject.name)
        )).all()

        subject_perf = [
            {
                "subject":  r.subject,
                "total":    r.total,
                "correct":  r.correct or 0,
                "accuracy": round((r.correct or 0) / r.total * 100, 1) if r.total else 0.0,
            }
            for r in subj_rows
        ]
        strongest = max(subject_perf, key=lambda s: s["accuracy"])["subject"] if subject_perf else None

        # Last active timestamp
        last_session_at = (await db.execute(
            select(ExamSession.completed_at)
            .where(*base_filter)
            .order_by(ExamSession.completed_at.desc())
            .limit(1)
        )).scalar_one_or_none()

        results.append({
            "student_id":         student.id,
            "name":               student.name,
            "email":              student.email,
            "streak_days":        streak,
            "total_sessions":     total_sessions,
            "total_questions":    total_questions,
            "neet_score":         neet_score,
            "strongest_subject":  strongest,
            "subject_performance": subject_perf,
            "last_active":        last_session_at.strftime("%b %d, %Y") if last_session_at else None,
        })

    return results
