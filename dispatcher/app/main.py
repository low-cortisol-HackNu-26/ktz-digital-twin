"""Dispatcher Service — Admin hub for railway telemetry system."""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import close_db, close_redis, init_db, init_redis
from app.routes import auth, dashboard, users, warnings
from app.routes import ingest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_startup_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Dispatcher Service starting...")
    await init_db()
    await init_redis()
    logger.info("Dispatcher Service ready on port 8002")
    yield
    logger.info("Dispatcher Service shutting down...")
    await close_redis()
    await close_db()
    logger.info("Dispatcher Service stopped")


app = FastAPI(
    title="Dispatcher Service",
    description="Admin hub — user management, manual warnings, fleet overview",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
_allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(ingest.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(warnings.router)
app.include_router(dashboard.router)


@app.get("/", summary="Service info", include_in_schema=False)
async def root() -> dict:
    return {"service": "dispatcher", "version": "2.0.0", "docs": "/docs"}


@app.get("/health", summary="Health check")
async def health() -> dict:
    return {
        "status": "healthy",
        "service": "dispatcher",
        "uptime_seconds": f"{time.time() - _startup_time:.1f}",
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
