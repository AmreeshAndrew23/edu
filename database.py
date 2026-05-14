from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Use SQLite for local development
    DATABASE_URL = "sqlite+aiosqlite:///./country.db"
elif "postgres" in DATABASE_URL:
    # Ensure asyncpg is used for Postgres
    if not DATABASE_URL.startswith("postgresql+asyncpg://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(engine, class_="AsyncSession", expire_on_commit=False)


async def get_db():
    async with async_session() as session:
        yield session