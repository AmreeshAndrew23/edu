from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Topic(Base, TimestampMixin):

    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)

    topic_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id"),
        nullable=False
    )

  