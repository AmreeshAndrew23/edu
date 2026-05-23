from datetime import datetime
from sqlalchemy import Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class ExamSession(Base, TimestampMixin):
    """
    One row per student exam attempt.
    subject_id and topic_id are nullable — they capture what the student
    chose to filter by (exam-only, exam+subject, or exam+subject+topic).
    """

    __tablename__ = "exam_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    exam_id: Mapped[int] = mapped_column(
        ForeignKey("exams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Null means student selected the full exam (no subject filter)
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id"),
        nullable=True,
    )

    # Null means student did not narrow down to a single topic
    topic_id: Mapped[int | None] = mapped_column(
        ForeignKey("topics.id"),
        nullable=True,
    )

    # 'in_progress' | 'completed' | 'abandoned'
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress")

    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)

    # Populated on submit
    correct_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # ── Relationships ────────────────────────────────────────────────────────

    student = relationship("Student", back_populates="sessions")
    exam = relationship("Exam")
    subject = relationship("Subject")
    topic = relationship("Topic")
    answers = relationship("StudentAnswer", back_populates="session", cascade="all, delete-orphan")
