from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.cors import CORSMiddleware

from .api.routes.auth import router as auth_router
from .api.routes.dispatcher import router as dispatcher_router
from .api.routes.sync import router as sync_router
from .api.routes.health import router as health_router
from .api.routes.map import router as map_router
from .api.routes.telemetry import router as telemetry_router
from .config import settings
from .core.loco_seeder import seed_locomotives_if_missing
from .core.route_seeder import seed_routes_if_empty
from .core.runtime_state import shutdown_runtime, startup_runtime
from .db.session import Base, engine
from .models import (  # noqa: F401
    AuthSession,
    CurrentSnapshot,
    DriverAccount,
    IngestionStat,
    Locomotive,
    LocomotiveWarning,
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
                await conn.execute(
                    text("ALTER TABLE telemetry_events ADD COLUMN IF NOT EXISTS track_condition VARCHAR(32)")
                )
                await conn.execute(
                    text("ALTER TABLE telemetry_events ADD COLUMN IF NOT EXISTS weather_condition VARCHAR(32)")
                )
                await conn.execute(
                    text("ALTER TABLE telemetry_events ADD COLUMN IF NOT EXISTS fuel_level_percent DOUBLE PRECISION")
                )
                await conn.execute(
                    text("ALTER TABLE telemetry_events ADD COLUMN IF NOT EXISTS brakes_temperature_c DOUBLE PRECISION")
                )
                await conn.execute(
                    text("ALTER TABLE telemetry_events ADD COLUMN IF NOT EXISTS traction_type VARCHAR(16)")
                )
                await conn.execute(
                    text("ALTER TABLE telemetry_events ADD COLUMN IF NOT EXISTS fuel_consumption_lph DOUBLE PRECISION")
                )
                await conn.execute(
                    text("ALTER TABLE telemetry_events ADD COLUMN IF NOT EXISTS energy_consumption_kwh DOUBLE PRECISION")
                )
                await conn.execute(
                    text("ALTER TABLE locomotives ADD COLUMN IF NOT EXISTS traction_type VARCHAR(16) DEFAULT 'electric'")
                )
                await conn.execute(
                    text("UPDATE locomotives SET traction_type = COALESCE(NULLIF(traction_type, ''), 'electric')")
                )
                await conn.execute(
                    text("ALTER TABLE locomotive_warnings ADD COLUMN IF NOT EXISTS source VARCHAR(16) DEFAULT 'system'")
                )
                await conn.execute(
                    text("ALTER TABLE locomotive_warnings ADD COLUMN IF NOT EXISTS target_type VARCHAR(16) DEFAULT 'locomotive'")
                )
                await conn.execute(
                    text("ALTER TABLE locomotive_warnings ADD COLUMN IF NOT EXISTS target_id VARCHAR(128) DEFAULT ''")
                )
                await conn.execute(
                    text("ALTER TABLE locomotive_warnings ADD COLUMN IF NOT EXISTS created_by VARCHAR(128)")
                )
                await conn.execute(
                    text("ALTER TABLE locomotive_warnings ADD COLUMN IF NOT EXISTS warning_metadata JSONB")
                )
                await conn.execute(
                    text("ALTER TABLE locomotive_warnings ADD COLUMN IF NOT EXISTS allowed_speed_kph_override DOUBLE PRECISION")
                )
                await conn.execute(
                    text("ALTER TABLE locomotive_warnings ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ")
                )
                await conn.execute(
                    text("ALTER TABLE locomotive_warnings ADD COLUMN IF NOT EXISTS status VARCHAR(16) DEFAULT 'active'")
                )
                await conn.execute(
                    text("ALTER TABLE locomotive_warnings ADD COLUMN IF NOT EXISTS cleared_at TIMESTAMPTZ")
                )
                await conn.execute(
                    text("UPDATE locomotive_warnings SET source = COALESCE(source, 'system')")
                )
                await conn.execute(
                    text("UPDATE locomotive_warnings SET target_type = COALESCE(target_type, 'locomotive')")
                )
                await conn.execute(
                    text("UPDATE locomotive_warnings SET target_id = COALESCE(NULLIF(target_id, ''), locomotive_id)")
                )
                await conn.execute(
                    text("UPDATE locomotive_warnings SET status = CASE WHEN active THEN 'active' ELSE COALESCE(NULLIF(status, ''), 'cleared') END")
                )
            logger.info("Database tables ready")
            break
        except (SQLAlchemyError, OSError) as exc:
            if attempt == 5:
                logger.warning("DB unavailable after 5 attempts: %s", exc)
                break
            logger.warning("DB init attempt %s/5 failed, retrying in 2s: %s", attempt, exc)
            await asyncio.sleep(2)

    from sqlalchemy import select as _select
    from .db.session import AsyncSessionLocal
    from .core.runtime_state import cached_routes as _cached_routes
    async with AsyncSessionLocal() as session:
        await seed_routes_if_empty(session)
        await seed_locomotives_if_missing(session)
        from .models.route import Route as _Route
        _cached_routes[:] = (await session.execute(_select(_Route))).scalars().all()

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
app.include_router(dispatcher_router, prefix="/api")
app.include_router(map_router, prefix="/api")
app.include_router(telemetry_router, prefix="/api")
app.include_router(sync_router, prefix="/api")
app.include_router(health_router)
app.include_router(ws_router)
