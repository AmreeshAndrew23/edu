from sqlalchemy import String, Date, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class Student(Base, TimestampMixin):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(25), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    date_of_birth: Mapped[Date] = mapped_column(Date, nullable=False)
    country_id: Mapped[int] = mapped_column(Integer, ForeignKey("countries.id"), nullable=False)
    state_id: Mapped[int] = mapped_column(Integer, ForeignKey("states.id"), nullable=False)
    current_difficulty: Mapped[str] = mapped_column(String(20), default="easy", nullable=False)

    country = relationship("Country")
    state = relationship("State")
    sessions = relationship("ExamSession", back_populates="student")
    study_goals = relationship("StudyGoal", back_populates="student")

    @property
    def name(self) -> str:
        return f"{self.first_name} {self.last_name}"
