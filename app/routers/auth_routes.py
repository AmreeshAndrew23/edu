from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import bcrypt

from app.core.database import get_db
from app.models.student import Student
from app.schemas.student_schema import (
    StudentRegisterRequest,
    StudentLoginRequest,
    StudentRegistrationResponse,
    StudentLoginResponse,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


@router.post("/register", response_model=StudentRegistrationResponse)
async def register(payload: StudentRegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = (await db.execute(
        select(Student).where(Student.email == payload.email)
    )).scalar_one_or_none()

    if existing:
        # Old rows (before auth was added) have no password_hash — let them re-register
        if existing.password_hash:
            raise HTTPException(status_code=400, detail="Email already registered")
        # Upgrade the incomplete old record in-place
        existing.first_name = payload.first_name
        existing.last_name = payload.last_name
        existing.phone = payload.phone or None
        existing.password_hash = _hash(payload.password)
        existing.date_of_birth = payload.date_of_birth
        existing.country_id = payload.country_id
        existing.state_id = payload.state_id
        await db.commit()
        await db.refresh(existing)
        return existing

    if payload.phone:
        dup = (await db.execute(
            select(Student).where(Student.phone == payload.phone)
        )).scalar_one_or_none()
        if dup:
            raise HTTPException(status_code=400, detail="Phone number already registered")

    student = Student(
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        phone=payload.phone or None,
        password_hash=_hash(payload.password),
        date_of_birth=payload.date_of_birth,
        country_id=payload.country_id,
        state_id=payload.state_id,
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student


@router.post("/login", response_model=StudentLoginResponse)
async def login(payload: StudentLoginRequest, db: AsyncSession = Depends(get_db)):
    identifier = payload.identifier.strip()

    # try email first, then phone
    student = (await db.execute(
        select(Student).where(Student.email == identifier)
    )).scalar_one_or_none()

    if not student:
        student = (await db.execute(
            select(Student).where(Student.phone == identifier)
        )).scalar_one_or_none()

    if not student or not _verify(payload.password, student.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return StudentLoginResponse(
        id=student.id,
        first_name=student.first_name,
        last_name=student.last_name,
        email=student.email,
        phone=student.phone,
    )
