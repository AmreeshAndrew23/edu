from sqlalchemy import Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base import TimestampMixin

class State(Base, TimestampMixin):

    __tablename__ = "states"

    id: Mapped[int] = mapped_column(primary_key=True)

    country_id: Mapped[int] = mapped_column(
        ForeignKey("countries.id", ondelete="CASCADE"),
        index=True
    )

    code: Mapped[str] = mapped_column(
        String(10),
        nullable=False
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    country = relationship(
        "Country",
        back_populates="states"
    )

    __table_args__ = (
        UniqueConstraint("country_id", "code"),
    )