import os
import logging

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


_raw_url = settings.DATABASE_URL
DATABASE_URL = (
    _raw_url
    .replace("postgres://", "postgresql://")
    .replace("postgresql://", "postgresql+asyncpg://")
)

logger.info("DB host: %s", DATABASE_URL.split("@")[-1].split("/")[0] if "@" in DATABASE_URL else "unknown")

engine = create_async_engine(
    DATABASE_URL,
    echo=os.environ.get("SQL_ECHO", "false").lower() == "true",
    # timeout=10: asyncpg will raise after 10s if it can't connect
    connect_args={"timeout": 10},
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
