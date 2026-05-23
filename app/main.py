import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.routers.country_routes import router as country_router
from app.routers.student_routes import router as student_router
from app.routers.exam_routers import router as exam_router
from app.routers.session_routes import router as session_router
from app.routers.subjects_routes import router as subject_router
from app.routers.topic_routes import router as topic_router
from app.routers.ai_routes import router as ai_router
from app.routers.question_routes import router as question_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Max-Age": "86400",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.database import AsyncSessionLocal, engine
    from app.models import (  # noqa: F401 – ensure all models are registered
        Country, State, Student, Subject, Topic,
        Exam, ExamBlueprint, Question, ExamSession, StudentAnswer,
    )
    from app.core.database import Base

    logger.info("=== Creating any missing DB tables ===")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("=== DB tables ready ===")
    except Exception as exc:
        logger.error("=== create_all failed: %s ===", exc)

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
    response = await call_next(request)
    for key, value in CORS_HEADERS.items():
        response.headers[key] = value
    return response


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/health/db")
async def health_db():
    from app.core.database import AsyncSessionLocal
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "healthy", "db": "connected"}
    except Exception as exc:
        logger.error("DB health check failed: %s", exc)
        return JSONResponse(status_code=503, content={"status": "unhealthy", "db": str(exc)})


app.include_router(country_router)
app.include_router(student_router)
app.include_router(exam_router)
app.include_router(session_router)
app.include_router(subject_router)
app.include_router(topic_router)
app.include_router(ai_router)
app.include_router(question_router)
