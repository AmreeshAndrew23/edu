from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db

from app.models.question import Question
from app.schemas.question_schema import QuestionCreate, QuestionRead
from app.services.question_service import QuestionService  

router = APIRouter(
    prefix="/questions",
    tags=["Questions"]
)

@router.post("/", response_model=QuestionRead)
async def create_question(
    payload: QuestionCreate,
    db: AsyncSession = Depends(get_db)
):
    try:
        question = await QuestionService.create_question(db, payload)
        return question
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
   