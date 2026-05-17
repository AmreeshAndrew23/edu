from fastapi import HTTPException
from app.models.student import Student
from app.models.state import State
from app.repositories.student_repository import StudentRepository


class StudentService:

    @staticmethod
    async def register(db, payload):

        # 1. Duplicate check
        existing = await StudentRepository.get_by_email(db, payload.email)
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        # 2. Validate state-country relationship
        state = await db.get(State, payload.state_id)

        if not state or state.country_id != payload.country_id:
            raise HTTPException(
                status_code=400,
                detail="Invalid state for selected country"
            )

        # 3. Create student object
        student = Student(
            name=payload.name,
            email=payload.email,
            date_of_birth=payload.date_of_birth,
            country_id=payload.country_id,
            state_id=payload.state_id
        )

        # 4. Save
        return await StudentRepository.create(db, student)