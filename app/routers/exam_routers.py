from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException
from app.core.database import get_db
from app.models.exam import Exam

router = APIRouter(
    prefix="/exams",
    tags=["Exams"]
)

@router.get("/", response_model=Exam)
async def get_exams(db: AsyncSession = Depends(get_db)):

    result = await db.execute(select(Exam))
    exams = result.scalars().all()
    return exams

