from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from .api.routes.auth import router as auth_router
from .config import settings
from .db.session import Base, engine
from .models import user as _user_models  # noqa: F401

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        db_url = make_url(settings.DATABASE_URL)
        logger.info(
            "Database target: driver=%s host=%s port=%s db=%s user=%s",
            db_url.drivername,
            db_url.host,
            db_url.port,
            db_url.database,
            db_url.username,
        )
    except (TypeError, ValueError, SQLAlchemyError):  # pragma: no cover
        logger.warning("Could not parse DATABASE_URL")

    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            logger.info("Database initialization successful")
            break
        except (SQLAlchemyError, OSError) as exc:  # pragma: no cover
            if attempt == max_attempts:
                logger.warning("Database unavailable during startup: %s", exc)
                break
            logger.warning(
                "Database init attempt %s/%s failed: %s. Retrying in 1s...",
                attempt,
                max_attempts,
                exc,
            )
            await asyncio.sleep(1)
    yield


app = FastAPI(title="KTZ Digital Twin API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router, prefix="/api")
