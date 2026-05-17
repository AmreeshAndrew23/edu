from sqlalchemy import String,Date, Integer,ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

class Student(Base, TimestampMixin):
    __tablename__ = "students"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    date_of_birth: Mapped[Date] = mapped_column(Date, nullable=False)
    country_id: Mapped[int] = mapped_column(Integer, ForeignKey("countries.id"), nullable=False)
    state_id: Mapped[int] = mapped_column(Integer, ForeignKey("states.id"), nullable=False)


    country = relationship("Country")
    state = relationship("State")