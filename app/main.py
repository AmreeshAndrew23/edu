import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.routers.auth_routes import router as auth_router
from app.routers.country_routes import router as country_router
from app.routers.student_routes import router as student_router
from app.routers.exam_routers import router as exam_router
from app.routers.session_routes import router as session_router
from app.routers.subjects_routes import router as subject_router
from app.routers.topic_routes import router as topic_router
from app.routers.ai_routes import router as ai_router
from app.routers.question_routes import router as question_router
from app.routers.chat_routes import router as chat_router
from app.routers.dashboard_routes import router as dashboard_router
from app.routers.analytics_routes import router as analytics_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Max-Age": "86400",
}


async def _background_seed():
    from app.core.database import AsyncSessionLocal
    from app.seed.seed_all import seed_all
    try:
        async with AsyncSessionLocal() as db:
            await seed_all(db)
        logger.info("=== Seed complete ===")
    except Exception as exc:
        logger.error("=== Seed failed: %s ===", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.database import engine, Base
    from app.models import (  # noqa: F401
        Country, State, Student, Subject, Topic,
        Exam, ExamBlueprint, Question, ExamSession, StudentAnswer, ChatLog, AiUsageLog,
        StudyGoal, GoalProgress,
    )

    # Retry DB connection — Railway PostgreSQL may not be ready immediately
    logger.info("=== Waiting for DB connection ===")
    for _attempt in range(10):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("=== DB tables ready ===")
            break
        except Exception as exc:
            logger.warning("DB not ready (attempt %d/10): %s", _attempt + 1, exc)
            if _attempt == 9:
                raise
            await asyncio.sleep(3)

    # Run each migration independently — a failing ALTER won't roll back table creation
    _migrations = [
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS first_name VARCHAR(50)",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS last_name VARCHAR(50)",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS phone VARCHAR(25)",
        "ALTER TABLE students ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)",
        "ALTER TABLE students ALTER COLUMN name DROP NOT NULL",
        "ALTER TABLE questions ADD COLUMN IF NOT EXISTS source VARCHAR(20) NOT NULL DEFAULT 'ai_generated'",
        "ALTER TABLE questions ADD COLUMN IF NOT EXISTS neet_year INTEGER",
        "ALTER TABLE questions ADD COLUMN IF NOT EXISTS paper_order INTEGER",
    ]
    for _sql in _migrations:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(_sql))
        except Exception as exc:
            logger.warning("Migration skipped: %s — %s", _sql[:60], exc)

    logger.info("=== Running seed ===")
    await _background_seed()
    logger.info("=== Seed complete — server ready ===")

    yield


app = FastAPI(
    title="QuizThala",
    version="1.0.0",
    description="A application built for NEET COACHING",
    lifespan=lifespan,
)


@app.middleware("http")
async def cors_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return Response(status_code=200, headers=CORS_HEADERS)
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        response = Response(status_code=500, content="Internal Server Error")
    for key, value in CORS_HEADERS.items():
        response.headers[key] = value
    return response


@app.get("/")
async def root():
    return {
        "message": "QuizThala API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "health_db": "/health/db",
    }


@app.get("/debug/exam/{exam_id}")
async def debug_exam(exam_id: int, db: AsyncSession = Depends(get_db)):
    """Debug single exam"""
    from sqlalchemy import func
    from app.models.exam import Exam
    from app.models.exam_blueprint import ExamBlueprint
    from app.models.subject import Subject
    from app.models.topic import Topic

    exam = await db.get(Exam, exam_id)
    if not exam:
        return {"error": f"Exam {exam_id} not found"}

    exam_subject = await db.get(Subject, exam.subject_id)

    # Count blueprints
    bp_count = (await db.execute(
        select(func.count(ExamBlueprint.id))
        .where(ExamBlueprint.exam_id == exam_id)
    )).scalar()

    # Get blueprints by subject
    bp_by_subject = (await db.execute(
        select(Subject.name, func.count(ExamBlueprint.id).label("count"))
        .join(Topic, Topic.subject_id == Subject.id)
        .join(ExamBlueprint, ExamBlueprint.topic_id == Topic.id)
        .where(ExamBlueprint.exam_id == exam_id)
        .group_by(Subject.name)
    )).all()

    return {
        "exam_id": exam_id,
        "exam_name": exam.exam_name,
        "exam_year": exam.exam_year,
        "exam_subject": exam_subject.name if exam_subject else None,
        "total_blueprints": bp_count,
        "blueprints_by_subject": {name: count for name, count in bp_by_subject},
    }


@app.get("/debug/blueprints")
async def debug_blueprints(db: AsyncSession = Depends(get_db)):
    """Debug endpoint to check what blueprints exist in DB"""
    from sqlalchemy import func
    from app.models.exam import Exam
    from app.models.exam_blueprint import ExamBlueprint
    from app.models.subject import Subject
    from app.models.topic import Topic

    # Get all exams
    exams = (await db.execute(select(Exam).order_by(Exam.exam_year.desc()))).scalars().all()

    result = {}
    for exam in exams:
        # Count blueprints per exam per subject
        subjects_data = (await db.execute(
            select(
                Subject.name,
                func.count(ExamBlueprint.id).label("bp_count")
            )
            .join(Topic, Topic.subject_id == Subject.id)
            .join(ExamBlueprint, ExamBlueprint.topic_id == Topic.id)
            .where(ExamBlueprint.exam_id == exam.id)
            .group_by(Subject.name)
        )).all()

        result[f"{exam.exam_name} {exam.exam_year}"] = {
            "id": exam.id,
            "subjects": {name: count for name, count in subjects_data}
        }

    return result


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/health/db")
async def health_db():
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import func, select
    from app.models.exam import Exam
    from app.models.exam_blueprint import ExamBlueprint
    from app.models.question import Question
    try:
        async with AsyncSessionLocal() as session:
            exams    = (await session.execute(select(func.count()).select_from(Exam))).scalar()
            bps      = (await session.execute(select(func.count()).select_from(ExamBlueprint))).scalar()
            qs       = (await session.execute(select(func.count()).select_from(Question))).scalar()
        return {"status": "healthy", "exams": exams, "blueprints": bps, "questions": qs}
    except Exception as exc:
        logger.error("DB health check failed: %s", exc)
        return JSONResponse(status_code=503, content={"status": "unhealthy", "db": str(exc)})


app.include_router(auth_router)
app.include_router(country_router)
app.include_router(student_router)
app.include_router(exam_router)
app.include_router(session_router)
app.include_router(subject_router)
app.include_router(topic_router)
app.include_router(ai_router)
app.include_router(question_router)
app.include_router(chat_router)
app.include_router(dashboard_router)
app.include_router(analytics_router)
