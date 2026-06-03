import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, cast, case, Date, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.models.exam_session import ExamSession
from app.models.student_answer import StudentAnswer
from app.models.question import Question
from app.models.topic import Topic
from app.models.subject import Subject

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# NEET exam question distribution
_NEET_Q = {"Physics": 45, "Chemistry": 45, "Biology": 90}
_NEET_MAX = 720

# Cutoffs in descending order: (score, display_label, tier_key)
_CUTOFFS = [
    (650, "AIIMS / Top MBBS",           "elite"),
    (600, "Top Govt. Medical College",   "top_govt"),
    (500, "Govt. Medical College",       "govt"),
    (400, "Private Medical College",     "private"),
    (0,   "Needs More Practice",         "needs_work"),
]


# ── Schemas ───────────────────────────────────────────────────────────────────

class SubjectPerf(BaseModel):
    subject: str
    accuracy: float
    total: int
    correct: int


class WeakArea(BaseModel):
    topic_id: int
    topic_name: str
    accuracy: float
    total: int
    wrong: int


class RecentSession(BaseModel):
    session_id: int
    date: str
    subject_name: str
    correct: int
    total: int
    percentage: float
    marks: int


class NeetEstimate(BaseModel):
    estimated_score: int
    max_score: int
    percentage: float
    tier_label: str
    tier_key: str
    message: str


class DashboardStats(BaseModel):
    total_sessions: int
    total_marks: int
    total_questions_attempted: int
    streak_days: int
    subject_performance: list[SubjectPerf]
    strongest_subject: str | None
    weak_areas: list[WeakArea]
    neet_estimate: NeetEstimate
    recent_sessions: list[RecentSession]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _compute_streak(session_dates: set[date]) -> int:
    if not session_dates:
        return 0
    today = date.today()
    # Allow today or yesterday as the start (so early-morning users keep streak)
    start = today if today in session_dates else today - timedelta(days=1)
    streak, check = 0, start
    while check in session_dates:
        streak += 1
        check -= timedelta(days=1)
    return streak


def _neet_estimate(correct: int, wrong: int, total: int) -> NeetEstimate:
    """
    Scale the student's actual last-50-question performance to /720.
    Formula: (correct*4 - wrong*1) / (total*4)  × 720
    """
    if total == 0:
        score = 0
    else:
        actual_marks = correct * 4 - wrong * 1
        max_marks    = total * 4
        score = max(0, min(_NEET_MAX, round(actual_marks / max_marks * _NEET_MAX)))

    pct = round(score / _NEET_MAX * 100, 1)

    tier_label = tier_key = ""
    for cutoff, label, key in _CUTOFFS:
        if score >= cutoff:
            tier_label, tier_key = label, key
            break

    message = "Targeting top medical colleges — keep it up!"
    for cutoff, label, _ in reversed(_CUTOFFS):
        if cutoff > score:
            gap = cutoff - score
            message = f"{gap} more marks to reach {cutoff} ({label})"
            break

    return NeetEstimate(
        estimated_score=score,
        max_score=_NEET_MAX,
        percentage=pct,
        tier_label=tier_label,
        tier_key=tier_key,
        message=message,
    )


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(student_id: int, db: AsyncSession = Depends(get_db)):
    """Single endpoint that returns all dashboard metrics for a student."""

    base_filter = [
        ExamSession.student_id == student_id,
        ExamSession.status == "completed",
    ]

    # ── 1. Total sessions ────────────────────────────────────────────────────
    total_sessions = (await db.execute(
        select(func.count()).select_from(ExamSession).where(*base_filter)
    )).scalar() or 0

    # ── 2. Correct / wrong counts → NEET marks ──────────────────────────────
    correct_count = (await db.execute(
        select(func.count()).select_from(StudentAnswer)
        .join(ExamSession, ExamSession.id == StudentAnswer.session_id)
        .where(*base_filter, StudentAnswer.is_correct == True)  # noqa: E712
    )).scalar() or 0

    wrong_count = (await db.execute(
        select(func.count()).select_from(StudentAnswer)
        .join(ExamSession, ExamSession.id == StudentAnswer.session_id)
        .where(
            *base_filter,
            StudentAnswer.is_correct == False,           # noqa: E712
            StudentAnswer.selected_option.isnot(None),
        )
    )).scalar() or 0

    total_questions = (await db.execute(
        select(func.count()).select_from(StudentAnswer)
        .join(ExamSession, ExamSession.id == StudentAnswer.session_id)
        .where(*base_filter)
    )).scalar() or 0

    total_marks = correct_count * 4 - wrong_count

    # ── 3. Streak ────────────────────────────────────────────────────────────
    date_rows = (await db.execute(
        select(cast(ExamSession.completed_at, Date).label("d"))
        .where(*base_filter, ExamSession.completed_at.isnot(None))
        .distinct()
        .order_by(cast(ExamSession.completed_at, Date).desc())
    )).all()

    session_dates = {r.d for r in date_rows if r.d is not None}
    streak_days   = _compute_streak(session_dates)

    # ── 4. Subject performance ───────────────────────────────────────────────
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
        SubjectPerf(
            subject=r.subject,
            total=r.total,
            correct=r.correct or 0,
            accuracy=round((r.correct or 0) / r.total * 100, 1) if r.total else 0.0,
        )
        for r in subj_rows
    ]

    strongest = (
        max(subject_perf, key=lambda s: s.accuracy).subject
        if subject_perf else None
    )

    # ── 5. Weak areas (top 3, min 3 attempts) ────────────────────────────────
    weak_rows = (await db.execute(
        select(
            Question.topic_id,
            Topic.topic_name,
            func.count(StudentAnswer.id).label("total"),
            func.sum(case((StudentAnswer.is_correct == False, 1), else_=0)).label("wrong"),  # noqa: E712
        )
        .join(StudentAnswer, StudentAnswer.question_id == Question.id)
        .join(ExamSession,   ExamSession.id == StudentAnswer.session_id)
        .join(Topic,         Topic.id       == Question.topic_id)
        .where(*base_filter)
        .group_by(Question.topic_id, Topic.topic_name)
        .having(func.count(StudentAnswer.id) >= 3)
        .order_by(
            func.sum(case((StudentAnswer.is_correct == False, 1), else_=0)).desc()  # noqa: E712
        )
        .limit(3)
    )).all()

    weak_areas = [
        WeakArea(
            topic_id=r.topic_id,
            topic_name=r.topic_name,
            total=r.total,
            wrong=r.wrong or 0,
            accuracy=round((1 - (r.wrong or 0) / r.total) * 100, 1) if r.total else 0.0,
        )
        for r in weak_rows
    ]

    # ── 6. Recent sessions ───────────────────────────────────────────────────
    recent_rows = (await db.execute(
        select(
            ExamSession.id,
            ExamSession.completed_at,
            ExamSession.correct_count,
            ExamSession.total_questions,
            ExamSession.score_percentage,
            Subject.name.label("subject_name"),
        )
        .outerjoin(Subject, Subject.id == ExamSession.subject_id)
        .where(*base_filter)
        .order_by(ExamSession.completed_at.desc())
        .limit(5)
    )).all()

    recent_sessions = []
    for r in recent_rows:
        correct  = r.correct_count or 0
        total    = r.total_questions or 0
        wrong    = total - correct           # approximate (skipped counted as wrong)
        marks    = correct * 4 - wrong * 1
        pct      = round(r.score_percentage or 0, 1)
        date_str = r.completed_at.strftime("%b %d") if r.completed_at else "—"
        recent_sessions.append(RecentSession(
            session_id=r.id,
            date=date_str,
            subject_name=r.subject_name or "Full NEET",
            correct=correct,
            total=total,
            percentage=pct,
            marks=marks,
        ))

    # ── 7. NEET score estimate (last 50 answered questions, scaled to /720) ────
    last50_subq = (
        select(StudentAnswer.is_correct)
        .join(ExamSession, ExamSession.id == StudentAnswer.session_id)
        .where(*base_filter, StudentAnswer.selected_option.isnot(None))
        .order_by(StudentAnswer.id.desc())
        .limit(50)
        .subquery()
    )
    n50_row = (await db.execute(
        select(
            func.sum(case((last50_subq.c.is_correct == True, 1), else_=0)).label("correct"),  # noqa: E712
            func.count().label("total"),
        ).select_from(last50_subq)
    )).one()

    n50_correct = n50_row.correct or 0
    n50_total   = n50_row.total   or 0
    n50_wrong   = n50_total - n50_correct
    neet_estimate = _neet_estimate(n50_correct, n50_wrong, n50_total)

    return DashboardStats(
        total_sessions=total_sessions,
        total_marks=total_marks,
        total_questions_attempted=total_questions,
        streak_days=streak_days,
        subject_performance=subject_perf,
        strongest_subject=strongest,
        weak_areas=weak_areas,
        neet_estimate=neet_estimate,
        recent_sessions=recent_sessions,
    )


# ── Calendar schemas ──────────────────────────────────────────────────────────

class DayActivity(BaseModel):
    date: str
    sessions: int
    marks: int
    accuracy: float


class CalendarData(BaseModel):
    days: list[DayActivity]


class DailySession(BaseModel):
    session_id: int
    subject_name: str
    correct: int
    total: int
    marks: int
    percentage: float


class DailyStats(BaseModel):
    date: str
    sessions: list[DailySession]
    total_marks: int
    total_questions: int


# ── Calendar endpoints ────────────────────────────────────────────────────────

@router.get("/calendar", response_model=CalendarData)
async def get_calendar_data(
    student_id: int,
    year: int,
    month: int,
    db: AsyncSession = Depends(get_db),
):
    """Per-day session activity for a given month."""
    from calendar import monthrange
    last_day = monthrange(year, month)[1]
    start = date(year, month, 1)
    end   = date(year, month, last_day)

    rows = (await db.execute(
        select(
            cast(ExamSession.completed_at, Date).label("d"),
            func.count(ExamSession.id).label("session_count"),
            func.sum(func.coalesce(ExamSession.correct_count, 0)).label("total_correct"),
            func.sum(func.coalesce(ExamSession.total_questions, 0)).label("total_qs"),
            func.avg(ExamSession.score_percentage).label("avg_pct"),
        )
        .where(
            ExamSession.student_id == student_id,
            ExamSession.status == "completed",
            ExamSession.completed_at.isnot(None),
            cast(ExamSession.completed_at, Date) >= start,
            cast(ExamSession.completed_at, Date) <= end,
        )
        .group_by(cast(ExamSession.completed_at, Date))
        .order_by(cast(ExamSession.completed_at, Date))
    )).all()

    days = []
    for r in rows:
        correct = r.total_correct or 0
        total   = r.total_qs or 0
        wrong   = total - correct
        marks   = correct * 4 - wrong
        days.append(DayActivity(
            date=r.d.strftime("%Y-%m-%d"),
            sessions=r.session_count,
            marks=marks,
            accuracy=round(float(r.avg_pct or 0), 1),
        ))

    return CalendarData(days=days)


@router.get("/daily", response_model=DailyStats)
async def get_daily_stats(
    student_id: int,
    date_str: str = Query(..., alias="date"),
    db: AsyncSession = Depends(get_db),
):
    """Individual session results for a specific date (YYYY-MM-DD)."""
    target = date.fromisoformat(date_str)

    rows = (await db.execute(
        select(
            ExamSession.id,
            ExamSession.correct_count,
            ExamSession.total_questions,
            ExamSession.score_percentage,
            Subject.name.label("subject_name"),
        )
        .outerjoin(Subject, Subject.id == ExamSession.subject_id)
        .where(
            ExamSession.student_id == student_id,
            ExamSession.status == "completed",
            ExamSession.completed_at.isnot(None),
            cast(ExamSession.completed_at, Date) == target,
        )
        .order_by(ExamSession.completed_at)
    )).all()

    sessions, total_marks, total_questions = [], 0, 0
    for r in rows:
        correct = r.correct_count or 0
        total   = r.total_questions or 0
        wrong   = total - correct
        marks   = correct * 4 - wrong
        total_marks     += marks
        total_questions += total
        sessions.append(DailySession(
            session_id=r.id,
            subject_name=r.subject_name or "Full NEET",
            correct=correct,
            total=total,
            marks=marks,
            percentage=round(float(r.score_percentage or 0), 1),
        ))

    return DailyStats(
        date=date_str,
        sessions=sessions,
        total_marks=total_marks,
        total_questions=total_questions,
    )
