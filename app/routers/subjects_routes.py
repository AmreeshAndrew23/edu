from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException

from app.core.database import get_db
from app.models.subject import Subject

router = APIRouter(
    prefix="/subjects",
    tags=["Subjects"]
)

@router.get("/", response_model=list[Subject])

async def get_subjects(db: AsyncSession = Depends(get_db)):

    result = await db.execute(select(Subject))
    subjects = result.scalars().all()
    return subjects 

