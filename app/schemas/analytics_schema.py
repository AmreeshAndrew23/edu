from datetime import date, datetime
from pydantic import BaseModel


# ── Progress Timeline ──────────────────────────────────────────────────────

class ProgressPoint(BaseModel):
    date: date
    score_percentage: float
    estimated_neet_score: int
    questions_attempted: int
    correct_count: int


class ProgressTimeline(BaseModel):
    total_points: int
    points: list[ProgressPoint]


# ── Mastery Levels ──────────────────────────────────────────────────────

class MasteryLevel(BaseModel):
    subject: str
    level: str  # 'beginner' | 'intermediate' | 'expert'
    accuracy: float
    attempts: int


class MasteryLevelResponse(BaseModel):
    mastery_levels: list[MasteryLevel]


# ── Weak Topic Alerts ──────────────────────────────────────────────────────

class WeakTopicAlert(BaseModel):
    topic_id: int
    topic_name: str
    subject: str
    accuracy: float
    attempts: int
    correct_count: int
    wrong_count: int


class WeakTopicsResponse(BaseModel):
    total_weak_topics: int
    alerts: list[WeakTopicAlert]


# ── Study Goals ──────────────────────────────────────────────────────────

class StudyGoalRequest(BaseModel):
    goal_type: str  # 'daily' | 'weekly' | 'monthly'
    target_questions: int
    target_minutes: int


class StudyGoalResponse(BaseModel):
    id: int
    student_id: int
    goal_type: str
    target_questions: int
    target_minutes: int
    start_date: datetime
    end_date: datetime | None
    status: str

    class Config:
        from_attributes = True


class GoalProgressEntry(BaseModel):
    date: date
    questions_completed: int
    minutes_spent: int
    goal_met: bool


class StudyGoalProgressResponse(BaseModel):
    goal_id: int
    goal_type: str
    target_questions: int
    target_minutes: int
    total_questions_completed: int
    total_minutes_spent: int
    days_goal_met: int
    progress_entries: list[dict]
