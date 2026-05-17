from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.student import Student


class StudentRepository:

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str):
        result = await db.execute(
            select(Student).where(Student.email == email)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, student: Student):
        db.add(student)
        await db.commit()
        await db.refresh(student)
        return student