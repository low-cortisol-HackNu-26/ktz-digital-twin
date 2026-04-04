from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.cors import CORSMiddleware

from .api.routes.auth import router as auth_router
from .api.routes.health import router as health_router
from .api.routes.map import router as map_router
from .api.routes.telemetry import router as telemetry_router
from .config import settings
from .core.runtime_state import shutdown_runtime, startup_runtime
from .db.session import Base, engine
from .models import (  # noqa: F401
    AuthSession,
    CurrentSnapshot,
    DriverAccount,
    IngestionStat,
    Locomotive,
    LocomotivePosition,
    Route,
    TelemetryEventRecord,
)
from .ws.handler import router as ws_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await startup_runtime()

    try:
        db_url = make_url(settings.DATABASE_URL)
        logger.info(
            "Database: driver=%s host=%s port=%s db=%s",
            db_url.drivername, db_url.host, db_url.port, db_url.database,
        )
    except (TypeError, ValueError, SQLAlchemyError):
        logger.warning("Could not parse DATABASE_URL")

    for attempt in range(1, 6):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables ready")
            break
        except (SQLAlchemyError, OSError) as exc:
            if attempt == 5:
                logger.warning("DB unavailable after 5 attempts: %s", exc)
                break
            logger.warning("DB init attempt %s/5 failed, retrying in 2s: %s", attempt, exc)
            await asyncio.sleep(2)

    yield

    await shutdown_runtime()
    await engine.dispose()


app = FastAPI(
    title="KTZ Digital Twin API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(map_router, prefix="/api")
app.include_router(telemetry_router, prefix="/api")
app.include_router(health_router)
app.include_router(ws_router)
