import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.database import AsyncSessionLocal
    logger.info("=== QuizThala starting — testing DB connection ===")
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        logger.info("=== DB connection OK ===")
    except Exception as exc:
        logger.error("=== DB connection FAILED: %s ===", exc)
    yield
    logger.info("=== QuizThala shutting down ===")


app = FastAPI(
    title="QuizThala",
    version="1.0.0",
    description="A application built for NEET COACHING",
    lifespan=lifespan,
)

_allowed = os.environ.get("FRONTEND_URL", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_allowed] if _allowed != "*" else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled %s on %s %s: %s",
                 type(exc).__name__, request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {exc}"},
    )


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
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "db": str(exc)},
        )


app.include_router(country_router)
app.include_router(student_router)
app.include_router(exam_router)
app.include_router(session_router)
app.include_router(subject_router)
app.include_router(topic_router)
app.include_router(ai_router)
app.include_router(question_router)
