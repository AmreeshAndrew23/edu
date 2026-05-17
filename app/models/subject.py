from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Subject(Base, TimestampMixin):

    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False
    )

    exams = relationship(
        "Exam",
        back_populates="subject"
    )

    topics = relationship(
        "Topic",
        back_populates="subject"
    )