from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Question(Base, TimestampMixin):

    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)

    exam_id: Mapped[int] = mapped_column(
        ForeignKey("exams.id", ondelete="CASCADE")
    )

    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE")
    )

    question_text: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    option_a: Mapped[str] = mapped_column(Text)
    option_b: Mapped[str] = mapped_column(Text)
    option_c: Mapped[str] = mapped_column(Text)
    option_d: Mapped[str] = mapped_column(Text)

    correct_option: Mapped[str] = mapped_column(
        String(1),
        nullable=False
    )

    explanation: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )

    difficulty_level: Mapped[str] = mapped_column(
        String(20),
        nullable=True
    )

    exam = relationship("Exam")
    topic = relationship("Topic")