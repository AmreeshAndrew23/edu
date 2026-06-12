import logging
from datetime import datetime, timedelta
from sqlalchemy import select, func, desc, Integer, case
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException

from app.core.database import get_db
from app.models.student import Student
from app.models.exam_session import ExamSession
from app.models.student_answer import StudentAnswer
from app.models.question import Question
from app.models.topic import Topic
from app.models.subject import Subject
from app.models.study_goal import StudyGoal, GoalProgress
from app.schemas.analytics_schema import (
    ProgressTimeline,
    ProgressPoint,
    MasteryLevel,
    MasteryLevelResponse,
    WeakTopicAlert,
    WeakTopicsResponse,
    StudyGoalRequest,
    StudyGoalResponse,
    StudyGoalProgressResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])


# ── Difficulty Level ──────────────────────────────────────────────────────

@router.get("/difficulty-level", response_model=dict)
async def get_difficulty_level(
    student_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get student's current difficulty level and recent performance."""
    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Get last 3 sessions for trend
    recent = (await db.execute(
        select(ExamSession)
        .where(
            ExamSession.student_id == student_id,
            ExamSession.status == "completed",
        )
        .order_by(ExamSession.completed_at.desc())
        .limit(3)
    )).scalars().all()

    scores = [s.score_percentage or 0 for s in recent]
    avg_score = sum(scores) / len(scores) if scores else 0

    return {
        "current_difficulty": student.current_difficulty,
        "recent_scores": scores,
        "average_score": round(avg_score, 1),
        "sessions_completed": len(recent),
    }


# ── Progress Timeline ──────────────────────────────────────────────────────

@router.get("/progress-timeline", response_model=ProgressTimeline)
async def get_progress_timeline(
    student_id: int,
    days: int = 90,
    db: AsyncSession = Depends(get_db),
) -> ProgressTimeline:
    """
    Get student's score progression over time.
    Shows estimated NEET score for each day they completed a quiz.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Get all completed sessions for this student in the date range
    sessions = (await db.execute(
        select(ExamSession)
        .where(
            ExamSession.student_id == student_id,
            ExamSession.status == "completed",
            ExamSession.completed_at >= cutoff_date,
        )
        .order_by(ExamSession.completed_at)
    )).scalars().all()

    points: list[ProgressPoint] = []

    for session in sessions:
        if session.score_percentage is not None and session.completed_at:
            # Calculate estimated NEET score (4 marks per correct, -1 for wrong)
            total_questions = session.total_questions
            correct = session.correct_count or 0
            wrong = total_questions - correct
            estimated_score = (correct * 4) + (wrong * -1)

            points.append(ProgressPoint(
                date=session.completed_at.date(),
                score_percentage=round(session.score_percentage, 2),
                estimated_neet_score=estimated_score,
                questions_attempted=total_questions,
                correct_count=correct,
            ))

    return ProgressTimeline(
        total_points=len(points),
        points=points,
    )


# ── Subject Mastery Levels ──────────────────────────────────────────────────

@router.get("/mastery-levels", response_model=MasteryLevelResponse)
async def get_mastery_levels(
    student_id: int,
    min_attempts: int = 3,
    db: AsyncSession = Depends(get_db),
) -> MasteryLevelResponse:
    """
    Calculate mastery level for each subject (Beginner/Intermediate/Expert).
    Requires minimum number of attempts to count.

    - Beginner: < 50% accuracy
    - Intermediate: 50-75% accuracy
    - Expert: > 75% accuracy
    """
    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Get all subjects
    subjects = (await db.execute(
        select(Subject).where(Subject.name.in_(["Physics", "Chemistry", "Biology"]))
    )).scalars().all()

    mastery_levels: list[MasteryLevel] = []

    for subject in subjects:
        # Get accuracy for this subject
        result = await db.execute(
            select(
                func.count(StudentAnswer.id).label("total"),
                func.sum(case((StudentAnswer.is_correct == True, 1), else_=0)).label("correct"),
            )
            .select_from(StudentAnswer)
            .join(Question, StudentAnswer.question_id == Question.id)
            .join(Topic, Question.topic_id == Topic.id)
            .join(ExamSession, StudentAnswer.session_id == ExamSession.id)
            .where(
                ExamSession.student_id == student_id,
                Topic.subject_id == subject.id,
                ExamSession.status == "completed",
            )
        )
        row = result.one()
        total = row.total or 0
        correct = row.correct or 0

        if total < min_attempts:
            level = "beginner"
            accuracy = 0.0
        else:
            accuracy = round((correct / total) * 100, 2) if total > 0 else 0.0
            if accuracy >= 75:
                level = "expert"
            elif accuracy >= 50:
                level = "intermediate"
            else:
                level = "beginner"

        mastery_levels.append(MasteryLevel(
            subject=subject.name,
            level=level,
            accuracy=accuracy,
            attempts=total,
        ))

    return MasteryLevelResponse(mastery_levels=mastery_levels)


# ── Weak Topic Alerts ──────────────────────────────────────────────────────

@router.get("/weak-topics-alert", response_model=WeakTopicsResponse)
async def get_weak_topics_alert(
    student_id: int,
    accuracy_threshold: float = 70,
    min_attempts: int = 3,
    db: AsyncSession = Depends(get_db),
) -> WeakTopicsResponse:
    """
    Get topics where student is scoring below accuracy_threshold.
    These are topics that need attention.
    """
    # Get weak topics from dashboard query (same logic)
    weak_areas = (await db.execute(
        select(
            Topic.id,
            Topic.topic_name,
            Subject.name.label("subject"),
            func.count(StudentAnswer.id).label("total"),
            func.sum(case((StudentAnswer.is_correct == True, 1), else_=0)).label("correct"),
        )
        .select_from(StudentAnswer)
        .join(Question, StudentAnswer.question_id == Question.id)
        .join(ExamSession, StudentAnswer.session_id == ExamSession.id)
        .join(Topic, Question.topic_id == Topic.id)
        .join(Subject, Topic.subject_id == Subject.id)
        .where(
            ExamSession.student_id == student_id,
            ExamSession.status == "completed",
        )
        .group_by(Topic.id, Topic.topic_name, Subject.name)
    )).all()

    alerts: list[WeakTopicAlert] = []

    for row in weak_areas:
        topic_id, topic_name, subject, total, correct = row
        correct = correct or 0
        accuracy = round((correct / total) * 100, 2) if total >= min_attempts else 0

        if accuracy < accuracy_threshold and total >= min_attempts:
            alerts.append(WeakTopicAlert(
                topic_id=topic_id,
                topic_name=topic_name,
                subject=subject,
                accuracy=accuracy,
                attempts=total,
                correct_count=correct,
                wrong_count=total - correct,
            ))

    # Sort by accuracy (lowest first)
    alerts.sort(key=lambda x: x.accuracy)

    return WeakTopicsResponse(
        total_weak_topics=len(alerts),
        alerts=alerts[:10],  # Top 10 weakest topics
    )


# ── Study Goals ──────────────────────────────────────────────────────────

@router.post("/goals/create", response_model=StudyGoalResponse)
async def create_study_goal(
    student_id: int,
    request: StudyGoalRequest,
    db: AsyncSession = Depends(get_db),
) -> StudyGoalResponse:
    """
    Create a new study goal (daily/weekly/monthly).
    """
    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    goal = StudyGoal(
        student_id=student_id,
        goal_type=request.goal_type,  # 'daily' | 'weekly' | 'monthly'
        target_questions=request.target_questions,
        target_minutes=request.target_minutes,
        status="active",
    )
    db.add(goal)
    await db.commit()
    await db.refresh(goal)

    logger.info(f"Created {request.goal_type} goal for student {student_id}")

    return StudyGoalResponse.model_validate(goal)


@router.get("/goals/active", response_model=list[StudyGoalResponse])
async def get_active_goals(
    student_id: int,
    db: AsyncSession = Depends(get_db),
) -> list[StudyGoalResponse]:
    """
    Get all active study goals for a student.
    """
    goals = (await db.execute(
        select(StudyGoal)
        .where(
            StudyGoal.student_id == student_id,
            StudyGoal.status == "active",
        )
    )).scalars().all()

    return [StudyGoalResponse.model_validate(g) for g in goals]


@router.get("/goals/progress/{goal_id}", response_model=StudyGoalProgressResponse)
async def get_goal_progress(
    goal_id: int,
    student_id: int,
    db: AsyncSession = Depends(get_db),
) -> StudyGoalProgressResponse:
    """
    Get progress for a specific study goal.
    """
    goal = await db.get(StudyGoal, goal_id)
    if not goal or goal.student_id != student_id:
        raise HTTPException(status_code=404, detail="Goal not found")

    # Get progress entries
    progress_entries = (await db.execute(
        select(GoalProgress)
        .where(GoalProgress.goal_id == goal_id)
        .order_by(desc(GoalProgress.progress_date))
    )).scalars().all()

    total_questions = sum(p.questions_completed for p in progress_entries)
    total_minutes = sum(p.minutes_spent for p in progress_entries)
    days_met = sum(1 for p in progress_entries if p.goal_met)

    return StudyGoalProgressResponse(
        goal_id=goal.id,
        goal_type=goal.goal_type,
        target_questions=goal.target_questions,
        target_minutes=goal.target_minutes,
        total_questions_completed=total_questions,
        total_minutes_spent=total_minutes,
        days_goal_met=days_met,
        progress_entries=[
            {
                "date": p.progress_date.date(),
                "questions_completed": p.questions_completed,
                "minutes_spent": p.minutes_spent,
                "goal_met": p.goal_met,
            }
            for p in progress_entries
        ],
    )


@router.post("/goals/update-progress/{goal_id}")
async def update_goal_progress(
    goal_id: int,
    student_id: int,
    questions_completed: int,
    minutes_spent: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Update progress for a study goal.
    Called after each quiz completion.
    """
    goal = await db.get(StudyGoal, goal_id)
    if not goal or goal.student_id != student_id:
        raise HTTPException(status_code=404, detail="Goal not found")

    today = datetime.utcnow().date()

    # Check if progress entry exists for today
    existing = (await db.execute(
        select(GoalProgress)
        .where(
            GoalProgress.goal_id == goal_id,
            func.date(GoalProgress.progress_date) == today,
        )
    )).scalar()

    goal_met = (questions_completed >= goal.target_questions) and (minutes_spent >= goal.target_minutes)

    if existing:
        existing.questions_completed += questions_completed
        existing.minutes_spent += minutes_spent
        existing.goal_met = goal_met
    else:
        new_progress = GoalProgress(
            goal_id=goal_id,
            progress_date=datetime.utcnow(),
            questions_completed=questions_completed,
            minutes_spent=minutes_spent,
            goal_met=goal_met,
        )
        db.add(new_progress)

    await db.commit()
    logger.info(f"Updated progress for goal {goal_id}")

    return {"status": "updated", "goal_met": goal_met}
