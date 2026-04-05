"""Main FastAPI application for backup queue service."""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import close_db, get_db, init_db
from .models import DispatcherQueueItem, TelemetryQueueItem
from .schemas import (
    DispatcherQueueStatusResponse,
    DispatcherSyncResponse,
    HealthResponse,
    QueueDispatcherRequest,
    QueueDispatcherResponse,
    QueueItemDetail,
    QueueStatusResponse,
    QueueTelemetryRequest,
    QueueTelemetryResponse,
    SyncResponse,
    TelemetryItemDetail,
)
from .sync_manager import dispatcher_sync_manager, sync_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_startup_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing backup queue service...")
    await init_db()
    await sync_manager.start()
    await dispatcher_sync_manager.start()
    logger.info("Backup queue service ready")
    yield
    logger.info("Shutting down backup queue service...")
    await dispatcher_sync_manager.stop()
    await sync_manager.stop()
    await close_db()
    logger.info("Backup queue service stopped")


app = FastAPI(
    title="Backup Queue Service",
    description="Offline buffering for telemetry (→ backend) and dispatcher events (→ dispatcher)",
    version="2.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Telemetry queue (existing — client → backend)
# ---------------------------------------------------------------------------

telemetry_router = APIRouter(prefix="/api/queue/telemetry", tags=["telemetry-queue"])


@telemetry_router.post(
    "",
    response_model=QueueTelemetryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Queue telemetry event (store-and-forward to backend)",
)
async def queue_telemetry(
    raw: Request,
    db: AsyncSession = Depends(get_db),
) -> QueueTelemetryResponse:
    """
    Accept a telemetry event from the client.

    Accepts two formats:
    - Wrapped: {"locomotive_id": "...", "event": {...}, "source": "..."}
    - Raw flat event (from simulator): {"locomotive_id": "...", "speed_kph": ..., ...}

    - If the backend is reachable → forwards immediately and marks as synced.
    - If not → stores in local SQLite and retries in the background every 30 s.
    """
    try:
        body = await raw.json()

        # Support both wrapped and raw (simulator) formats
        if "event" in body and isinstance(body["event"], dict):
            locomotive_id = body.get("locomotive_id", "unknown")
            event_data = body["event"]
            source = body.get("source", "client")
        else:
            locomotive_id = body.get("locomotive_id", "unknown")
            event_data = body
            source = body.get("source", "simulator")

        queue_item = TelemetryQueueItem(
            locomotive_id=locomotive_id,
            event_data=event_data,
            source=source,
        )
        db.add(queue_item)
        await db.flush()

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

        await db.commit()
        return QueueTelemetryResponse(
            queued=True,
            queue_id=queue_item.id,
            backend_status="unreachable" if not sync_manager.backend_reachable else "reachable",
            message="Event queued for later sync",
        )

    except Exception as exc:
        logger.error(f"Error queueing telemetry: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to queue event: {exc}")


@telemetry_router.post("/sync", response_model=SyncResponse, summary="Manually trigger telemetry sync")
async def manual_telemetry_sync() -> SyncResponse:
    result = await sync_manager.sync()
    return SyncResponse(
        synced_count=result["synced"],
        failed_count=result["failed"],
        remaining_count=result["remaining"],
        backend_reachable=sync_manager.backend_reachable,
    )


@telemetry_router.get("/items", response_model=list[TelemetryItemDetail], summary="List telemetry queue items")
async def list_telemetry_items(
    pending_only: bool = True,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> list[TelemetryItemDetail]:
    """List items in the telemetry queue. pending_only=true shows only unsynced items."""
    query = select(TelemetryQueueItem)
    if pending_only:
        query = query.where(TelemetryQueueItem.synced_at.is_(None))
    query = query.order_by(TelemetryQueueItem.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return [TelemetryItemDetail.model_validate(i) for i in result.scalars().all()]


@telemetry_router.get("/status", response_model=QueueStatusResponse, summary="Telemetry queue status")
async def telemetry_queue_status(db: AsyncSession = Depends(get_db)) -> QueueStatusResponse:
    unsync = await db.execute(
        select(func.count(TelemetryQueueItem.id)).where(TelemetryQueueItem.synced_at.is_(None))
    )
    synced = await db.execute(
        select(func.count(TelemetryQueueItem.id)).where(TelemetryQueueItem.synced_at.isnot(None))
    )
    oldest = await db.execute(
        select(TelemetryQueueItem.created_at)
        .where(TelemetryQueueItem.synced_at.is_(None))
        .order_by(TelemetryQueueItem.created_at)
        .limit(1)
    )
    return QueueStatusResponse(
        queued_count=unsync.scalar() or 0,
        synced_count=synced.scalar() or 0,
        backend_reachable=sync_manager.backend_reachable,
        last_sync_at=sync_manager.last_sync_at,
        last_error=sync_manager.last_error,
        oldest_queued_at=oldest.scalar(),
    )


# ---------------------------------------------------------------------------
# Dispatcher queue (new — client → dispatcher)
# ---------------------------------------------------------------------------

dispatcher_router = APIRouter(prefix="/api/queue/dispatcher", tags=["dispatcher-queue"])


@dispatcher_router.post(
    "",
    response_model=QueueDispatcherResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Queue event for dispatcher (store-and-forward)",
)
async def queue_dispatcher_event(
    request: QueueDispatcherRequest,
    db: AsyncSession = Depends(get_db),
) -> QueueDispatcherResponse:
    """
    Accept any event destined for the dispatcher.

    **Flow:**
    1. Stores the event in local SQLite immediately (never loses data).
    2. If dispatcher is reachable right now → forwards immediately.
    3. If not → background task retries every 15 s with exponential backoff.

    **auth_token** — pass your dispatcher JWT here. The queue service will use it
    when forwarding. If the token expires before the dispatcher comes back, the item
    is skipped and you'll need to re-queue with a fresh token.

    **Common uses:**
    - `endpoint: /api/warnings` — create a manual warning
    - `endpoint: /api/dispatcher/fleet` — any fleet update
    """
    try:
        item = DispatcherQueueItem(
            event_type=request.event_type,
            endpoint=request.endpoint,
            payload=request.payload,
            auth_token=request.auth_token,
            source=request.source or "client",
            target_url=request.target_url,
        )
        db.add(item)
        await db.flush()

        # Try immediate forward if dispatcher is up
        if dispatcher_sync_manager.dispatcher_reachable:
            success = await dispatcher_sync_manager._forward(db, item)
            if success:
                await db.commit()
                return QueueDispatcherResponse(
                    queued=True,
                    queue_id=item.id,
                    dispatcher_status="reachable",
                    message="Event forwarded to dispatcher immediately",
                )

        await db.commit()
        return QueueDispatcherResponse(
            queued=True,
            queue_id=item.id,
            dispatcher_status="unreachable" if not dispatcher_sync_manager.dispatcher_reachable else "reachable",
            message="Dispatcher unreachable — event stored, will retry automatically",
        )

    except Exception as exc:
        logger.error(f"Error queueing dispatcher event: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to queue event: {exc}")


@dispatcher_router.post("/sync", response_model=DispatcherSyncResponse, summary="Manually trigger dispatcher sync")
async def manual_dispatcher_sync() -> DispatcherSyncResponse:
    result = await dispatcher_sync_manager.sync()
    return DispatcherSyncResponse(
        synced_count=result["synced"],
        failed_count=result["failed"],
        remaining_count=result["remaining"],
        dispatcher_reachable=dispatcher_sync_manager.dispatcher_reachable,
    )


@dispatcher_router.get("/items", response_model=list[QueueItemDetail], summary="List dispatcher queue items")
async def list_dispatcher_items(
    pending_only: bool = True,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> list[QueueItemDetail]:
    """List items in the dispatcher queue. pending_only=true shows only unsynced items."""
    query = select(DispatcherQueueItem)
    if pending_only:
        query = query.where(DispatcherQueueItem.synced_at.is_(None))
    query = query.order_by(DispatcherQueueItem.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return [QueueItemDetail.model_validate(i) for i in result.scalars().all()]


@dispatcher_router.get("/status", response_model=DispatcherQueueStatusResponse, summary="Dispatcher queue status")
async def dispatcher_queue_status(db: AsyncSession = Depends(get_db)) -> DispatcherQueueStatusResponse:
    unsync = await db.execute(
        select(func.count(DispatcherQueueItem.id)).where(DispatcherQueueItem.synced_at.is_(None))
    )
    synced = await db.execute(
        select(func.count(DispatcherQueueItem.id)).where(DispatcherQueueItem.synced_at.isnot(None))
    )
    oldest = await db.execute(
        select(DispatcherQueueItem.created_at)
        .where(DispatcherQueueItem.synced_at.is_(None))
        .order_by(DispatcherQueueItem.created_at)
        .limit(1)
    )
    return DispatcherQueueStatusResponse(
        queued_count=unsync.scalar() or 0,
        synced_count=synced.scalar() or 0,
        dispatcher_reachable=dispatcher_sync_manager.dispatcher_reachable,
        last_sync_at=dispatcher_sync_manager.last_sync_at,
        last_error=dispatcher_sync_manager.last_error,
        oldest_queued_at=oldest.scalar(),
    )


# ---------------------------------------------------------------------------
# Health & root
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, summary="Health check")
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    tq = await db.execute(
        select(func.count(TelemetryQueueItem.id)).where(TelemetryQueueItem.synced_at.is_(None))
    )
    dq = await db.execute(
        select(func.count(DispatcherQueueItem.id)).where(DispatcherQueueItem.synced_at.is_(None))
    )
    t_size = tq.scalar() or 0
    d_size = dq.scalar() or 0
    total = t_size + d_size

    if sync_manager.backend_reachable and dispatcher_sync_manager.dispatcher_reachable and total == 0:
        health_status = "healthy"
    elif total > 1000:
        health_status = "unhealthy"
    else:
        health_status = "degraded" if total > 0 else "healthy"

    return HealthResponse(
        status=health_status,
        backend_reachable=sync_manager.backend_reachable,
        dispatcher_reachable=dispatcher_sync_manager.dispatcher_reachable,
        queue_size=t_size,
        dispatcher_queue_size=d_size,
        uptime_seconds=time.time() - _startup_time,
    )


@app.get("/", summary="Service info", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"service": "backup-queue", "version": "2.0.0", "docs": "/docs"}


app.include_router(telemetry_router)
app.include_router(dispatcher_router)
