from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String

from app.core.database import Base


class AiUsageLog(Base):
    __tablename__ = "ai_usage_logs"

    id                 = Column(Integer, primary_key=True, index=True)
    student_id         = Column(Integer, ForeignKey("students.id", ondelete="SET NULL"), nullable=True)
    endpoint           = Column(String(100))   # "question_generation" | "neet_upload" | "chat"
    model              = Column(String(50))
    prompt_tokens      = Column(Integer, default=0)
    completion_tokens  = Column(Integer, default=0)
    total_tokens       = Column(Integer, default=0)
    estimated_cost_usd = Column(Float, nullable=True)
    context            = Column(String(500), nullable=True)
    created_at         = Column(DateTime, default=datetime.utcnow)
