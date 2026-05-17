from fastapi import FastAPI
from app.routers.country_routes import router as country_router
from app.seed.location_seed import seed_locations
from app.core.database import AsyncSessionLocal
from app.routers.student_routes import router as student_router



app = FastAPI(
    title="QuizThala",
    version="1.0.0",
    description="A application built for NEET COACHING",
)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.on_event("startup")
async def startup_event():
    async with AsyncSessionLocal() as db:
        await seed_locations(db)

app.include_router(country_router)

app.include_router(student_router)