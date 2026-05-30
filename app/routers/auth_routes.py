import secrets
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import bcrypt

from app.core.database import get_db
from app.core.email import send_otp_email
from app.models.student import Student
from app.schemas.student_schema import (
    StudentRegisterRequest,
    StudentLoginRequest,
    StudentRegistrationResponse,
    StudentLoginResponse,
    SendCodeRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Auth"])

# ── In-memory OTP store ────────────────────────────────────────────────────────
# email (lowercase) → {code: str, expires_at: datetime}
_otp_store: dict[str, dict] = {}

OTP_TTL_MINUTES = 10
OTP_RESEND_COOLDOWN_SECONDS = 60  # prevent spam


def _generate_otp(email: str) -> str:
    email = email.lower()
    existing = _otp_store.get(email)
    if existing:
        age = (datetime.utcnow() - existing["sent_at"]).total_seconds()
        if age < OTP_RESEND_COOLDOWN_SECONDS:
            raise HTTPException(
                status_code=429,
                detail=f"Please wait {int(OTP_RESEND_COOLDOWN_SECONDS - age)} seconds before requesting a new code.",
            )
    code = f"{secrets.randbelow(1_000_000):06d}"
    _otp_store[email] = {
        "code": code,
        "sent_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES),
    }
    return code


def _verify_otp(email: str, code: str) -> bool:
    email = email.lower()
    record = _otp_store.get(email)
    if not record:
        return False
    if datetime.utcnow() > record["expires_at"]:
        _otp_store.pop(email, None)
        return False
    return record["code"] == code


def _consume_otp(email: str) -> None:
    _otp_store.pop(email.lower(), None)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/send-code", summary="Send email verification OTP")
async def send_code(payload: SendCodeRequest):
    code = _generate_otp(payload.email)
    try:
        await send_otp_email(payload.email, code)
    except Exception as exc:
        logger.error("Email send failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to send email: {exc}")
    return {"message": "Verification code sent to your email."}


@router.post("/register", response_model=StudentRegistrationResponse)
async def register(payload: StudentRegisterRequest, db: AsyncSession = Depends(get_db)):
    if not _verify_otp(payload.email, payload.verification_code):
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification code. Please request a new one.",
        )
    _consume_otp(payload.email)

    existing = (await db.execute(
        select(Student).where(Student.email == payload.email)
    )).scalar_one_or_none()

    if existing:
        # Old rows (before auth was added) have no password_hash — let them re-register
        if existing.password_hash:
            raise HTTPException(status_code=400, detail="Email already registered")
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

    student = (await db.execute(
        select(Student).where(Student.email == identifier)
    )).scalar_one_or_none()

    if not student:
        student = (await db.execute(
            select(Student).where(Student.phone == identifier)
        )).scalar_one_or_none()

    if not student or not _verify_password(payload.password, student.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return StudentLoginResponse(
        id=student.id,
        first_name=student.first_name,
        last_name=student.last_name,
        email=student.email,
        phone=student.phone,
    )
