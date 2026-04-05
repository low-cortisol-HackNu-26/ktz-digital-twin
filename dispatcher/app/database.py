"""Database and Redis configuration for dispatcher service."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from typing import Optional

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://root:password@127.0.0.1:5433/locomotive_twin",
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

engine = create_async_engine(DB_URL, echo=False)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

_redis_client: Optional[Redis] = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_redis() -> Optional[Redis]:
    return _redis_client


async def init_db() -> None:
    """Create dispatcher-owned tables and verify connection."""
    from app.models.base import Base
    # Import all models so their tables are registered on Base.metadata
    import app.models.user  # noqa: F401
    import app.models.alert  # noqa: F401
    import app.models.telemetry_ingest  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Dispatcher database tables created / verified")


async def init_redis() -> None:
    """Connect to Redis (non-fatal if unavailable)."""
    global _redis_client
    try:
        client = Redis.from_url(REDIS_URL, decode_responses=True)
        await client.ping()
        _redis_client = client
        logger.info("Redis connection established")
    except Exception as exc:
        logger.warning(f"Redis unavailable — warnings will not push live updates: {exc}")
        _redis_client = None


async def close_db() -> None:
    await engine.dispose()


async def close_redis() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
