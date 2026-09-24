"""Database configuration and session management."""

from __future__ import annotations

import os
from pathlib import Path
from typing import AsyncGenerator, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# Load .env from project root
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass

logger = structlog.get_logger()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://ufn_user:changeme_in_production@localhost:5432/urban_flood",
)

# Build engine kwargs — add SSL for remote hosts
_engine_kwargs: dict = {"echo": False, "pool_size": 5, "max_overflow": 10}
if "aivencloud.com" in DATABASE_URL or "ssl=require" in DATABASE_URL:
    import ssl as _ssl
    _ctx = _ssl.create_default_context()
    _ctx.check_hostname = False
    _ctx.verify_mode = _ssl.CERT_NONE
    _engine_kwargs["connect_args"] = {"ssl": _ctx}
    # Remove ssl param from URL since we pass it via connect_args
    DATABASE_URL = DATABASE_URL.replace("?ssl=require", "").replace("&ssl=require", "")

engine = create_async_engine(DATABASE_URL, **_engine_kwargs)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)



class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""

    pass


# Track whether PostgreSQL is reachable
_db_online: Optional[bool] = None


async def verify_db_connectivity() -> bool:
    """Check if the database is actually reachable. Cached for the application lifetime."""
    global _db_online
    try:
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            _db_online = True
            return True
    except Exception:
        _db_online = False
        return False


async def get_db() -> AsyncGenerator[Optional[AsyncSession], None]:
    """FastAPI dependency: yields an async database session if available, else None instantly."""
    global _db_online
    if _db_online is None:
        await verify_db_connectivity()

    if _db_online is False:
        yield None
        return

    try:
        async with async_session() as session:
            try:
                yield session
                await session.commit()
                _db_online = True
            except Exception:
                await session.rollback()
                raise
    except Exception as e:
        _db_online = False
        logger.debug("Database session unavailable (standalone mode active)", error=str(e))
        yield None
