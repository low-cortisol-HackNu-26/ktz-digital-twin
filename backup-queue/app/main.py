"""Main FastAPI application for backup queue service."""

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import close_db, get_db, init_db
from .models import TelemetryQueueItem
from .schemas import (
    HealthResponse,
    QueueStatusResponse,
    QueueTelemetryRequest,
    QueueTelemetryResponse,
    SyncResponse,
)
from .sync_manager import sync_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Track startup time for uptime calculation
_startup_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    # Startup
    logger.info("Initializing backup queue service...")
    await init_db()
    await sync_manager.start()
    logger.info("Backup queue service ready")
    
    yield
    
    # Shutdown
    logger.info("Shutting down backup queue service...")
    await sync_manager.stop()
    await close_db()
    logger.info("Backup queue service stopped")


app = FastAPI(
    title="Backup Queue Service",
    description="Offline telemetry queueing and sync for railway locomotive monitoring",
    version="1.0.0",
    lifespan=lifespan,
)

router = APIRouter(prefix="/api/queue", tags=["queue"])


@router.post(
    "/telemetry",
    response_model=QueueTelemetryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Queue telemetry event",
)
async def queue_telemetry(
    request: QueueTelemetryRequest,
    db: AsyncSession = Depends(get_db),
) -> QueueTelemetryResponse:
    """
    Queue a telemetry event locally.
    
    If backend is reachable, attempts to send immediately.
    Otherwise, stores in SQLite queue for later sync.
    """
    try:
        # Create queue item
        queue_item = TelemetryQueueItem(
            locomotive_id=request.locomotive_id,
            event_data=request.event,
            source=request.source,
        )
        db.add(queue_item)
        await db.flush()  # Get the ID without committing yet
        
        # Check if backend is reachable and try immediate sync
        if sync_manager.backend_reachable:
            success = await sync_manager._sync_single(db, queue_item)
            if success:
                await db.commit()
                return QueueTelemetryResponse(
                    queued=True,
                    queue_id=queue_item.id,
                    backend_status="reachable",
                    message="Event sent to backend immediately",
                )
        
        # Backend unreachable or sync failed, keep in queue
        await db.commit()
        return QueueTelemetryResponse(
            queued=True,
            queue_id=queue_item.id,
            backend_status="unreachable" if not sync_manager.backend_reachable else "reachable",
            message="Event queued for later sync",
        )
    
    except Exception as e:
        logger.error(f"Error queueing telemetry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue event: {str(e)}",
        )


@router.post(
    "/sync",
    response_model=SyncResponse,
    summary="Manually trigger sync",
)
async def manual_sync() -> SyncResponse:
    """
    Manually trigger synchronization of queued events.
    Useful for testing or forcing sync without waiting for background task.
    """
    result = await sync_manager.sync()
    
    return SyncResponse(
        synced_count=result["synced"],
        failed_count=result["failed"],
        remaining_count=result["remaining"],
        backend_reachable=sync_manager.backend_reachable,
    )


@router.get(
    "/status",
    response_model=QueueStatusResponse,
    summary="Get queue status",
)
async def get_status(db: AsyncSession = Depends(get_db)) -> QueueStatusResponse:
    """
    Get current status of the backup queue.
    
    Returns:
    - queued_count: Number of events waiting to be synced
    - synced_count: Total number of events successfully synced (all time)
    - backend_reachable: Whether backend is currently reachable
    - last_sync_at: Timestamp of last sync attempt
    - oldest_queued_at: Timestamp of oldest unsync'd event
    """
    # Count unsync'd items
    unsync_result = await db.execute(
        select(func.count(TelemetryQueueItem.id)).where(
            TelemetryQueueItem.synced_at.is_(None)
        )
    )
    queued_count = unsync_result.scalar() or 0
    
    # Count synced items
    synced_result = await db.execute(
        select(func.count(TelemetryQueueItem.id)).where(
            TelemetryQueueItem.synced_at.isnot(None)
        )
    )
    synced_count = synced_result.scalar() or 0
    
    # Get oldest unsync'd item
    oldest_result = await db.execute(
        select(TelemetryQueueItem.created_at)
        .where(TelemetryQueueItem.synced_at.is_(None))
        .order_by(TelemetryQueueItem.created_at)
        .limit(1)
    )
    oldest_queued_at = oldest_result.scalar()
    
    return QueueStatusResponse(
        queued_count=queued_count,
        synced_count=synced_count,
        backend_reachable=sync_manager.backend_reachable,
        last_sync_at=sync_manager.last_sync_at,
        last_error=sync_manager.last_error,
        oldest_queued_at=oldest_queued_at,
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """
    Health check endpoint.
    
    Status levels:
    - healthy: All systems operational, backend reachable
    - degraded: Queue has items but working to sync
    - unhealthy: Unable to sync, large queue accumulation
    """
    # Count queue size
    queue_result = await db.execute(
        select(func.count(TelemetryQueueItem.id)).where(
            TelemetryQueueItem.synced_at.is_(None)
        )
    )
    queue_size = queue_result.scalar() or 0
    
    # Calculate uptime
    uptime = time.time() - _startup_time
    
    # Determine status
    if sync_manager.backend_reachable and queue_size == 0:
        status_str = "healthy"
    elif queue_size > 1000:  # Large backlog
        status_str = "unhealthy"
    else:
        status_str = "degraded" if queue_size > 0 else "healthy"
    
    return HealthResponse(
        status=status_str,
        backend_reachable=sync_manager.backend_reachable,
        queue_size=queue_size,
        uptime_seconds=uptime,
    )


@app.get("/", summary="Service info")
async def root() -> dict[str, str]:
    """Service information."""
    return {
        "service": "backup-queue",
        "version": "1.0.0",
        "docs": "/docs",
    }


# Include routers
app.include_router(router)
