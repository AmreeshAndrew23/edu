import os
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import AsyncSessionLocal
from app.seed.location_seed import seed_locations
from app.seed.seed_all import seed_all

from app.routers.country_routes import router as country_router
from app.routers.student_routes import router as student_router
from app.routers.exam_routers import router as exam_router
from app.routers.session_routes import router as session_router
from app.routers.subjects_routes import router as subject_router
from app.routers.topic_routes import router as topic_router
from app.routers.ai_routes import router as ai_router
from app.routers.question_routes import router as question_router

app = FastAPI(
    title="QuizThala",
    version="1.0.0",
    description="A application built for NEET COACHING",
)

_allowed = os.environ.get("FRONTEND_URL", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_allowed] if _allowed != "*" else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _run_seed() -> None:
    try:
        async with AsyncSessionLocal() as db:
            await seed_locations(db)
            await seed_all(db)
        print("Seed complete.")
    except Exception as exc:
        print(f"Seed error (non-fatal): {exc}")


@app.on_event("startup")
async def startup_event():
    # Schedule seed as a background task so the server starts immediately
    asyncio.create_task(_run_seed())


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


app.include_router(country_router)
app.include_router(student_router)
app.include_router(exam_router)
app.include_router(session_router)
app.include_router(subject_router)
app.include_router(topic_router)
app.include_router(ai_router)
app.include_router(question_router)
