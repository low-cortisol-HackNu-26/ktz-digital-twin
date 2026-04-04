from __future__ import annotations

import asyncio
import contextlib
import json
from contextlib import asynccontextmanager
from datetime import datetime
from time import perf_counter
from typing import Any

import redis.asyncio as redis
from fastapi import Body, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import TypeAdapter, ValidationError

from .config import settings
from .db import (
    close_db,
    connect_db,
    fetch_current_snapshot,
    fetch_history,
    fetch_ingestion_stats,
    fetch_latest_metrics,
    fetch_locomotives,
    increment_dropped_events,
    increment_invalid_events,
    persist_events,
)
from .metrics import metrics
from .schemas import IngestResult, PRIORITY_METRICS, TelemetryEvent
from .ws_manager import ws_manager


redis_client: redis.Redis | None = None
redis_subscriber_task: asyncio.Task | None = None
telemetry_adapter = TypeAdapter(TelemetryEvent)


async def redis_subscriber_loop() -> None:
    global redis_client
    if redis_client is None:
        return

    pubsub = redis_client.pubsub()
    await pubsub.subscribe(settings.redis_channel)

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if not message:
                await asyncio.sleep(0.01)
                continue

            data = message.get("data")
            if isinstance(data, bytes):
                payload = json.loads(data.decode("utf-8"))
            elif isinstance(data, str):
                payload = json.loads(data)
            else:
                continue

            loco_id = payload.get("locomotive_id")
            event_payload = payload.get("payload", payload)
            if loco_id:
                await ws_manager.broadcast_telemetry(loco_id, event_payload)
    finally:
        await pubsub.unsubscribe(settings.redis_channel)
        await pubsub.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    global redis_client
    global redis_subscriber_task

    await connect_db()
    redis_client = redis.from_url(settings.redis_url, decode_responses=False)
    await redis_client.ping()
    redis_subscriber_task = asyncio.create_task(redis_subscriber_loop())

    yield

    if redis_subscriber_task is not None:
        redis_subscriber_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await redis_subscriber_task
    if redis_client is not None:
        await redis_client.close()
    await close_db()


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    if redis_client is None:
        raise HTTPException(status_code=503, detail="redis not connected")
    return {"status": "ready"}


@app.post("/api/ingest/telemetry", response_model=IngestResult)
async def ingest_telemetry(payload: Any = Body(...)) -> IngestResult:
    if isinstance(payload, list):
        incoming = payload
    else:
        incoming = [payload]

    valid_events: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for idx, event_payload in enumerate(incoming):
        try:
            evt = telemetry_adapter.validate_python(event_payload)
            valid_events.append(evt.model_dump(mode="python"))
        except ValidationError as exc:
            errors.append({"index": idx, "errors": exc.errors()})

    invalid = len(errors)
    metrics.mark_invalid(invalid)
    await increment_invalid_events(invalid)

    if valid_events:
        await persist_events(valid_events)

        if redis_client is not None:
            for evt in valid_events:
                start = perf_counter()
                envelope = {
                    "type": "telemetry",
                    "locomotive_id": evt["locomotive_id"],
                    "payload": evt,
                }
                await redis_client.publish(settings.redis_channel, json.dumps(envelope, default=str))
                metrics.redis_publish_latency_ms = (perf_counter() - start) * 1000
                metrics.mark_valid(evt["locomotive_id"], evt["timestamp"])

    dropped = 0
    if not valid_events and invalid > 0:
        dropped = invalid
        metrics.mark_dropped(dropped)
        await increment_dropped_events(dropped)

    return IngestResult(accepted=len(valid_events), invalid=invalid, dropped=dropped, errors=errors)


@app.get("/api/locomotives")
async def get_locomotives() -> list[dict[str, Any]]:
    return await fetch_locomotives()


@app.get("/api/locomotives/{locomotive_id}/current")
async def get_current(locomotive_id: str) -> dict[str, Any]:
    snapshot = await fetch_current_snapshot(locomotive_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="locomotive not found")
    return snapshot


@app.get("/api/locomotives/{locomotive_id}/history")
async def get_history(
    locomotive_id: str,
    from_ts: datetime | None = Query(default=None, alias="from"),
    to_ts: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=200, ge=1, le=5000),
) -> dict[str, Any]:
    events = await fetch_history(locomotive_id, from_ts, to_ts, limit)
    return {"locomotive_id": locomotive_id, "events": events, "count": len(events)}


@app.get("/api/locomotives/{locomotive_id}/latest-metrics")
async def get_latest_metrics(locomotive_id: str) -> dict[str, Any]:
    result = await fetch_latest_metrics(locomotive_id, PRIORITY_METRICS)
    if result is None:
        raise HTTPException(status_code=404, detail="locomotive not found")
    return result


@app.get("/api/system/metrics")
async def get_system_metrics() -> dict[str, Any]:
    stats = await fetch_ingestion_stats()
    payload = metrics.to_dict(ws_manager.clients_count)
    payload.update(
        {
            "valid_events_count_db": stats.get("valid_events_count", 0),
            "invalid_events_count_db": stats.get("invalid_events_count", 0),
            "dropped_events_count_db": stats.get("dropped_events_count", 0),
            "updated_at": stats.get("updated_at"),
        }
    )
    return payload


@app.websocket("/ws/telemetry")
async def telemetry_stream(websocket: WebSocket, locomotive_id: str | None = None):
    await ws_manager.connect(websocket, locomotive_id)

    await websocket.send_json(
        {
            "type": "hello",
            "subscription": locomotive_id,
            "message": "connected",
        }
    )

    try:
        while True:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
            except json.JSONDecodeError:
                continue

            if msg.get("action") == "subscribe":
                await ws_manager.update_subscription(websocket, msg.get("locomotive_id"))
                await websocket.send_json(
                    {
                        "type": "subscribed",
                        "locomotive_id": msg.get("locomotive_id"),
                    }
                )
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
