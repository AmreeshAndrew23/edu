from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.student_schema import StudentRegisterRequest, StudentRegistrationResponse
from app.services.students_service import StudentService

router = APIRouter(prefix="/students", tags=["Students"])


@router.post("/Studentregister", response_model=StudentRegistrationResponse)
async def register_student(
    payload: StudentRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    return await StudentService.register(db, payload)
    