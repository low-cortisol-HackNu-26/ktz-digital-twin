from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis

from ..config import settings
from ..ws.manager import manager

TELEMETRY_CHANNEL = "telemetry.live"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ServiceMetrics:
    def __init__(self) -> None:
        self.valid_events_count = 0
        self.invalid_events_count = 0
        self.dropped_events_count = 0
        self.db_write_latency_ms = 0.0
        self.redis_publish_latency_ms = 0.0
        self.last_event_timestamp: str | None = None
        self.per_locomotive_last_seen: dict[str, str] = {}
        self._ingest_events_window: deque[float] = deque(maxlen=2_000)

    def record_ingested(self, *, valid: int = 0, invalid: int = 0, dropped: int = 0) -> None:
        now = time.monotonic()
        if valid > 0:
            self._ingest_events_window.extend(now for _ in range(valid))
        self.valid_events_count += valid
        self.invalid_events_count += invalid
        self.dropped_events_count += dropped

    def record_db_write_latency(self, latency_ms: float) -> None:
        self.db_write_latency_ms = latency_ms

    def record_redis_publish_latency(self, latency_ms: float) -> None:
        self.redis_publish_latency_ms = latency_ms

    def record_event_seen(self, locomotive_id: str, event_timestamp: datetime) -> None:
        ts = event_timestamp.astimezone(timezone.utc).isoformat()
        self.last_event_timestamp = ts
        self.per_locomotive_last_seen[locomotive_id] = ts

    def snapshot(self) -> dict[str, Any]:
        now = time.monotonic()
        while self._ingest_events_window and now - self._ingest_events_window[0] > 1.0:
            self._ingest_events_window.popleft()
        return {
            "ingest_rate_per_sec": len(self._ingest_events_window),
            "valid_events_count": self.valid_events_count,
            "invalid_events_count": self.invalid_events_count,
            "dropped_events_count": self.dropped_events_count,
            "db_write_latency_ms": round(self.db_write_latency_ms, 3),
            "redis_publish_latency_ms": round(self.redis_publish_latency_ms, 3),
            "ws_clients_count": manager.client_count,
            "last_event_timestamp": self.last_event_timestamp,
            "per_locomotive_last_seen": self.per_locomotive_last_seen,
        }


metrics = ServiceMetrics()
redis_client: Redis | None = None
_redis_listener_task: asyncio.Task[None] | None = None


async def startup_runtime() -> None:
    global redis_client, _redis_listener_task
    try:
        redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        await redis_client.ping()
        _redis_listener_task = asyncio.create_task(_listen_redis(), name="telemetry-redis-listener")
    except Exception:
        redis_client = None
        _redis_listener_task = None


async def shutdown_runtime() -> None:
    global _redis_listener_task, redis_client
    if _redis_listener_task is not None:
        _redis_listener_task.cancel()
        try:
            await _redis_listener_task
        except asyncio.CancelledError:
            pass
        _redis_listener_task = None

    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None


async def _listen_redis() -> None:
    if redis_client is None:
        return

    pubsub = redis_client.pubsub()
    await pubsub.subscribe(TELEMETRY_CHANNEL)
    try:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            payload = message.get("data")
            if not isinstance(payload, str):
                continue
            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                continue
            await manager.broadcast(event)
    except asyncio.CancelledError:
        raise
    finally:
        await pubsub.unsubscribe(TELEMETRY_CHANNEL)
        await pubsub.aclose()


async def publish_event(event: dict[str, Any]) -> None:
    if redis_client is None:
        await manager.broadcast(event)
        return

    started = time.perf_counter()
    try:
        await redis_client.publish(TELEMETRY_CHANNEL, json.dumps(event, ensure_ascii=True))
        elapsed = (time.perf_counter() - started) * 1000
        metrics.record_redis_publish_latency(elapsed)
    except Exception:
        await manager.broadcast(event)
