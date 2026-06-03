from sqlalchemy import Integer, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Question(Base, TimestampMixin):
    """
    An AI-generated MCQ question tied to a specific exam and topic.

    Correct option is stored as a single character: 'A', 'B', 'C', or 'D'.
    Questions are generated according to the ExamBlueprint's expected_questions
    and difficulty_level for each topic in a given exam year.
    """

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Which exam year this question belongs to (e.g. NEET 2026 - Physics)
    exam_id: Mapped[int] = mapped_column(
        ForeignKey("exams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Which topic within the exam this question covers
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    question_text: Mapped[str] = mapped_column(Text, nullable=False)

    option_a: Mapped[str] = mapped_column(Text, nullable=False)
    option_b: Mapped[str] = mapped_column(Text, nullable=False)
    option_c: Mapped[str] = mapped_column(Text, nullable=False)
    option_d: Mapped[str] = mapped_column(Text, nullable=False)

    # Single character: 'A' | 'B' | 'C' | 'D'
    correct_option: Mapped[str] = mapped_column(String(1), nullable=False)

    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 'easy' | 'medium' | 'hard' — inherited from blueprint's difficulty_level
    difficulty_level: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # 'ai_generated' | 'neet_paper'
    source: Mapped[str] = mapped_column(String(20), nullable=False, default='ai_generated')

    # Year the NEET paper was published (null for AI-generated questions)
    neet_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Relationships ────────────────────────────────────────────────────────

    exam = relationship("Exam", back_populates="questions")

    topic = relationship("Topic", back_populates="questions")
