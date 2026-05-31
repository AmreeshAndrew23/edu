from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.core.database import Base


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id                = Column(Integer, primary_key=True, index=True)
    student_id        = Column(Integer, ForeignKey("students.id", ondelete="SET NULL"), nullable=True)
    role              = Column(String(15))          # 'user' | 'assistant'
    message           = Column(Text)
    context           = Column(String(100), nullable=True)
    model             = Column(String(50), nullable=True)
    prompt_tokens     = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens      = Column(Integer, nullable=True)
    created_at        = Column(DateTime, default=datetime.utcnow)
