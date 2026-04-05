"""Sync manager for retrying failed uploads with exponential backoff."""

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .database import AsyncSessionLocal
from .models import DispatcherQueueItem, TelemetryQueueItem

logger = logging.getLogger(__name__)

# Retry configuration
MIN_BACKOFF = 1.0  # Start with 1 second
MAX_BACKOFF = 1800.0  # Cap at 30 minutes
BATCH_SIZE = 50


class SyncManager:
    """Syncs queued telemetry to the dispatcher (primary target)."""

    def __init__(self, backend_url: str = "http://dispatcher:8002", check_interval: int = 30):
        self.backend_url = backend_url
        self.ingest_url = f"{backend_url}/api/ingest/telemetry"
        self.check_interval = check_interval
        self.backend_reachable = True
        self.last_sync_at: datetime | None = None
        self.last_error: str | None = None
        self._sync_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the background sync task."""
        if self._sync_task is None:
            self._sync_task = asyncio.create_task(self._sync_loop())
            logger.info(f"SyncManager started, checking every {self.check_interval}s")

    async def stop(self) -> None:
        """Stop the background sync task."""
        if self._sync_task is not None:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
            logger.info("SyncManager stopped")

    async def _check_backend(self) -> bool:
        """Check if dispatcher (ingest target) is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.backend_url}/health", follow_redirects=True)
                reachable = response.status_code == 200
        except Exception as e:
            logger.warning(f"[dispatcher-ingest] health check failed: {e}")
            reachable = False
        if reachable != self.backend_reachable:
            logger.warning(f"[dispatcher-ingest] reachability changed → {'UP' if reachable else 'DOWN'}")
        return reachable

    async def _sync_loop(self) -> None:
        """Background task that periodically syncs queued events."""
        while True:
            try:
                await asyncio.sleep(self.check_interval)
                await self.sync()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in sync loop: {e}")

    async def sync(self) -> dict[str, int]:
        """Attempt to sync all unsync'd events. Returns count of synced/failed events."""
        # Check backend health
        self.backend_reachable = await self._check_backend()

        if not self.backend_reachable:
            remaining = await self._get_queue_count()
            logger.warning(f"[backend] unreachable — {remaining} item(s) waiting in queue")
            return {"synced": 0, "failed": 0, "remaining": remaining}

        async with AsyncSessionLocal() as db:
            # Get unsync'd items in batches
            unsync_items = await self._get_unsync_items(db, limit=BATCH_SIZE)

            if not unsync_items:
                logger.info("[backend] queue empty, nothing to sync")
                return {"synced": 0, "failed": 0, "remaining": 0}

            logger.info(f"[backend] syncing {len(unsync_items)} item(s)...")
            synced_count = 0
            failed_count = 0

            for item in unsync_items:
                success = await self._sync_single(db, item)
                if success:
                    synced_count += 1
                else:
                    failed_count += 1

            self.last_sync_at = datetime.now(timezone.utc)
            remaining = await self._get_queue_count(db)

            logger.info(
                f"Sync complete: {synced_count} synced, {failed_count} failed, {remaining} remaining"
            )
            return {"synced": synced_count, "failed": failed_count, "remaining": remaining}

    async def _get_unsync_items(
        self, db: AsyncSession, limit: int = BATCH_SIZE
    ) -> list[TelemetryQueueItem]:
        """Get items from queue that haven't been synced yet."""
        result = await db.execute(
            select(TelemetryQueueItem)
            .where(TelemetryQueueItem.synced_at.is_(None))
            .order_by(TelemetryQueueItem.created_at)
            .limit(limit)
        )
        return result.scalars().all()

    async def _sync_single(self, db: AsyncSession, item: TelemetryQueueItem) -> bool:
        """Try to sync a single item. Updates retry_count and error_message if failed."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.ingest_url, json=item.event_data)
                response.raise_for_status()

            # Mark as synced
            await db.execute(
                update(TelemetryQueueItem)
                .where(TelemetryQueueItem.id == item.id)
                .values(synced_at=datetime.now(timezone.utc), error_message=None)
            )
            await db.commit()
            logger.debug(f"Synced queue item {item.id}")
            return True

        except Exception as e:
            # Calculate next retry time with exponential backoff
            backoff = min(MAX_BACKOFF, MIN_BACKOFF * (2 ** item.retry_count))
            next_retry = datetime.now(timezone.utc)

            error_msg = str(e)
            self.last_error = error_msg

            await db.execute(
                update(TelemetryQueueItem)
                .where(TelemetryQueueItem.id == item.id)
                .values(
                    retry_count=item.retry_count + 1,
                    last_retry_at=next_retry,
                    error_message=error_msg,
                )
            )
            await db.commit()

            logger.warning(
                f"Failed to sync queue item {item.id}: {error_msg}. "
                f"Retry #{item.retry_count + 1} in {backoff:.0f}s"
            )
            return False

    async def _get_queue_count(self, db: AsyncSession | None = None) -> int:
        """Get count of unsync'd items in queue."""
        use_db = db is not None

        if not use_db:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(TelemetryQueueItem).where(TelemetryQueueItem.synced_at.is_(None))
                )
                return len(result.scalars().all())

        result = await db.execute(
            select(TelemetryQueueItem).where(TelemetryQueueItem.synced_at.is_(None))
        )
        return len(result.scalars().all())


# Global sync manager instance — picks up BACKEND_URL from env
sync_manager = SyncManager(backend_url=os.getenv("BACKEND_URL", "http://backend:8000"))


class DispatcherSyncManager:
    """Buffers client events and forwards them to the dispatcher when it is reachable."""

    def __init__(self, dispatcher_url: str = "http://dispatcher:8002", check_interval: int = 15):
        self.dispatcher_url = dispatcher_url
        self.check_interval = check_interval
        self.dispatcher_reachable = False
        self.last_sync_at: datetime | None = None
        self.last_error: str | None = None
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop(), name="dispatcher-sync")
            logger.info(f"DispatcherSyncManager started, checking every {self.check_interval}s")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _check_dispatcher(self) -> bool:
        # Both managers target the same host — reuse SyncManager's check result
        # to avoid two simultaneous health checks that can give conflicting answers.
        reachable = sync_manager.backend_reachable
        if reachable != self.dispatcher_reachable:
            logger.warning(f"[dispatcher] reachability changed → {'UP' if reachable else 'DOWN'}")
        return reachable

    async def _loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self.check_interval)
                await self.sync()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"DispatcherSyncManager error: {exc}")

    async def sync(self) -> dict[str, int]:
        self.dispatcher_reachable = await self._check_dispatcher()
        if not self.dispatcher_reachable:
            remaining = await self._queue_count()
            if remaining:
                logger.warning(f"[dispatcher] unreachable — {remaining} item(s) waiting in queue")
            return {"synced": 0, "failed": 0, "remaining": remaining}

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(DispatcherQueueItem)
                .where(DispatcherQueueItem.synced_at.is_(None))
                .order_by(DispatcherQueueItem.created_at)
                .limit(BATCH_SIZE)
            )
            items = result.scalars().all()

            if not items:
                return {"synced": 0, "failed": 0, "remaining": 0}

            logger.info(f"[dispatcher] syncing {len(items)} item(s)...")
            synced = failed = 0
            for item in items:
                ok = await self._forward(db, item)
                if ok:
                    synced += 1
                else:
                    failed += 1

            self.last_sync_at = datetime.now(timezone.utc)
            remaining = await self._queue_count(db)
            logger.info(f"Dispatcher sync: {synced} sent, {failed} failed, {remaining} remaining")
            return {"synced": synced, "failed": failed, "remaining": remaining}

    async def _forward(self, db: AsyncSession, item: DispatcherQueueItem) -> bool:
        # Build the full URL: target_url is the base, append endpoint if target_url is set
        if item.target_url:
            url = f"{item.target_url}{item.endpoint}"
        else:
            url = f"{self.dispatcher_url}{item.endpoint}"
        logger.debug(f"Forwarding dispatcher item {item.id}: target_url={item.target_url}, endpoint={item.endpoint}, final_url={url}")
        headers = {"Content-Type": "application/json"}
        
        # Handle different authentication schemes based on endpoint
        if item.auth_token:
            if item.endpoint == "/api/sync/users":
                # Internal sync endpoints use X-Sync-Secret header
                headers["X-Sync-Secret"] = item.auth_token
            else:
                # Dispatcher endpoints use Bearer token
                headers["Authorization"] = f"Bearer {item.auth_token}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(url, json=item.payload, headers=headers)

            if r.status_code == 401:
                # Token expired — mark permanently so it doesn't block the queue
                await db.execute(
                    update(DispatcherQueueItem)
                    .where(DispatcherQueueItem.id == item.id)
                    .values(
                        retry_count=item.retry_count + 1,
                        last_retry_at=datetime.now(timezone.utc),
                        error_message="token_expired: re-queue with fresh token",
                        synced_at=datetime.now(timezone.utc),  # skip it
                    )
                )
                await db.commit()
                logger.warning(f"Dispatcher queue item {item.id} skipped — token expired")
                return False

            r.raise_for_status()

            await db.execute(
                update(DispatcherQueueItem)
                .where(DispatcherQueueItem.id == item.id)
                .values(synced_at=datetime.now(timezone.utc), error_message=None)
            )
            await db.commit()
            logger.info(f"[dispatcher] forwarded item {item.id} → {item.endpoint}")
            return True

        except Exception as exc:
            self.last_error = str(exc)
            await db.execute(
                update(DispatcherQueueItem)
                .where(DispatcherQueueItem.id == item.id)
                .values(
                    retry_count=item.retry_count + 1,
                    last_retry_at=datetime.now(timezone.utc),
                    error_message=str(exc),
                )
            )
            await db.commit()
            logger.warning(f"Failed to forward dispatcher queue item {item.id}: {exc}")
            return False

    async def _queue_count(self, db: AsyncSession | None = None) -> int:
        async def _count(session: AsyncSession) -> int:
            r = await session.execute(
                select(DispatcherQueueItem).where(DispatcherQueueItem.synced_at.is_(None))
            )
            return len(r.scalars().all())

        if db is not None:
            return await _count(db)
        async with AsyncSessionLocal() as session:
            return await _count(session)


dispatcher_sync_manager = DispatcherSyncManager(
    dispatcher_url=os.getenv("DISPATCHER_URL", "http://dispatcher:8002")
)
