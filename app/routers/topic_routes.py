from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from app.core.database import get_db
from app.models.topic import Topic
from app.models.subject import Subject

router = APIRouter(prefix="/topics", tags=["Topics"])


class TopicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    topic_name: str
    subject_id: int


@router.get("/{subject_id}", response_model=list[TopicResponse])
async def get_topics_by_subject(subject_id: int, db: AsyncSession = Depends(get_db)):
    subject = await db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail=f"Subject {subject_id} not found")

    result = await db.execute(select(Topic).where(Topic.subject_id == subject_id))
    return result.scalars().all()
