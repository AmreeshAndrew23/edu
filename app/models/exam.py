from sqlalchemy import Integer, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Exam(Base, TimestampMixin):
    """
    Represents a NEET exam for a specific year and subject.
    e.g., NEET 2026 - Physics, NEET 2025 - Biology.
    One exam row per (year, subject) pair.
    """

    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    exam_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        # e.g. "NEET"
    )

    exam_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        # e.g. 2026
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id"),
        nullable=False,
    )

    # ── Relationships ────────────────────────────────────────────────────────

    subject = relationship(
        "Subject",
        back_populates="exams",
    )

    # All topic-level blueprint entries for this exam
    blueprints = relationship(
        "ExamBlueprint",
        back_populates="exam",
        cascade="all, delete-orphan",
    )

    # All questions generated from this exam's blueprints
    questions = relationship(
        "Question",
        back_populates="exam",
        cascade="all, delete-orphan",
    )
