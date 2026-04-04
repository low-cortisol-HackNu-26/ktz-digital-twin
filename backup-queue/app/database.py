"""Database initialization and session management for backup queue."""

import os
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Use environment variable or default to local SQLite
DB_URL = os.getenv("BACKUP_DB_URL", "sqlite+aiosqlite:///./backup_queue.db")

engine = create_async_engine(
    DB_URL,
    echo=False,
    connect_args={"timeout": 30} if "sqlite" in DB_URL else {},
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """Dependency for database sessions."""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create all tables."""
    async with engine.begin() as conn:
        from .models import Base
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()
