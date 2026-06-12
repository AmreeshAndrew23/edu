from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class StudyGoal(Base, TimestampMixin):
    """
    Track daily, weekly, and monthly study goals for students.
    goal_type: 'daily' | 'weekly' | 'monthly'
    """

    __tablename__ = "study_goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 'daily' | 'weekly' | 'monthly'
    goal_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # Target number of questions to solve
    target_questions: Mapped[int] = mapped_column(Integer, nullable=False)

    # Target time in minutes
    target_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    # Start date of this goal
    start_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # End date (null = ongoing)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 'active' | 'completed' | 'abandoned'
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    # ── Relationships ────────────────────────────────────────────────────────

    student = relationship("Student", back_populates="study_goals")
    progress = relationship("GoalProgress", back_populates="goal", cascade="all, delete-orphan")


class GoalProgress(Base, TimestampMixin):
    """
    Track daily progress towards study goals.
    """

    __tablename__ = "goal_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    goal_id: Mapped[int] = mapped_column(
        ForeignKey("study_goals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Date of this progress entry
    progress_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Questions solved on this date
    questions_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Time spent in minutes on this date
    minutes_spent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Whether goal was met on this date
    goal_met: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ── Relationships ────────────────────────────────────────────────────────

    goal = relationship("StudyGoal", back_populates="progress")
