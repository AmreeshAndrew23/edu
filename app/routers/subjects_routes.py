from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from app.core.database import get_db
from app.models.subject import Subject

router = APIRouter(prefix="/subjects", tags=["Subjects"])


class SubjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


@router.get("/", response_model=list[SubjectResponse])
async def get_subjects(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Subject).order_by(Subject.name))
    return result.scalars().all()
