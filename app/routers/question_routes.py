from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict

from app.core.database import get_db
from app.models.question import Question

router = APIRouter(prefix="/questions", tags=["Questions"])


class QuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exam_id: int
    topic_id: int
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    difficulty_level: str | None


@router.get("/", response_model=list[QuestionResponse])
async def list_questions(
    exam_id: int | None = None,
    topic_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List questions, optionally filtered by exam or topic."""
    query = select(Question)
    if exam_id:
        query = query.where(Question.exam_id == exam_id)
    if topic_id:
        query = query.where(Question.topic_id == topic_id)

    result = await db.execute(query)
    return result.scalars().all()
