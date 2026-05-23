from sqlalchemy import (
    Integer,
    String,
    ForeignKey,
    UniqueConstraint
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship
)

from app.core.database import Base
from app.models.base import TimestampMixin


class ExamBlueprint(Base, TimestampMixin):

    __tablename__ = "exam_blueprints"

    __table_args__ = (
        UniqueConstraint(
            "exam_id",
            "topic_id",
            name="uq_exam_topic"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    exam_id: Mapped[int] = mapped_column(
        ForeignKey("exams.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    weightage: Mapped[int] = mapped_column(
        Integer,
        nullable=True
    )

    expected_questions: Mapped[int] = mapped_column(
        Integer,
        nullable=True
    )

    difficulty_level: Mapped[str] = mapped_column(
        String(20),
        nullable=True
    )

    exam = relationship("Exam", back_populates="blueprints")

    topic = relationship("Topic", back_populates="blueprints")