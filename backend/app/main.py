from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.exc import SQLAlchemyError

from .api.routes.auth import router as auth_router
from .db.session import Base, engine
from .models import user as _user_models  # noqa: F401

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    except (SQLAlchemyError, OSError) as exc:  # pragma: no cover
        logger.warning("Database unavailable during startup: %s", exc)
    yield


app = FastAPI(title="KTZ Digital Twin API", version="1.0.0", lifespan=lifespan)
app.include_router(auth_router, prefix="/api")
