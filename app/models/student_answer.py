from sqlalchemy import Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class StudentAnswer(Base, TimestampMixin):
    """
    One row per question per session. selected_option is null if skipped.
    """

    __tablename__ = "student_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    session_id: Mapped[int] = mapped_column(
        ForeignKey("exam_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 'A' | 'B' | 'C' | 'D' — null means skipped
    selected_option: Mapped[str | None] = mapped_column(String(1), nullable=True)

    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Relationships ────────────────────────────────────────────────────────

    session = relationship("ExamSession", back_populates="answers")
    question = relationship("Question")
