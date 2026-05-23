import os
import ssl as ssl_lib
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

_is_local = any(h in DATABASE_URL for h in ("localhost", "127.0.0.1"))

# For Railway (non-local), use a permissive SSL context so asyncpg can negotiate
# SSL with the internal PostgreSQL without certificate verification issues.
_connect_args: dict = {}
if not _is_local:
    _ssl_ctx = ssl_lib.create_default_context()
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = ssl_lib.CERT_NONE
    _connect_args["ssl"] = _ssl_ctx

logger.info("DB configured: local=%s ssl=%s", _is_local, not _is_local)

engine = create_async_engine(
    DATABASE_URL,
    echo=os.environ.get("SQL_ECHO", "false").lower() == "true",
    connect_args=_connect_args,
    pool_pre_ping=True,   # ping connection before use; reconnect if stale
    pool_recycle=300,     # recycle connections every 5 min
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
