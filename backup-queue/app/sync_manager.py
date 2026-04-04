"""Sync manager for retrying failed uploads with exponential backoff."""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .database import AsyncSessionLocal
from .models import TelemetryQueueItem

logger = logging.getLogger(__name__)

# Retry configuration
MIN_BACKOFF = 1.0  # Start with 1 second
MAX_BACKOFF = 1800.0  # Cap at 30 minutes
BATCH_SIZE = 50


class SyncManager:
    """Manages syncing queued events to the backend."""

    def __init__(self, backend_url: str = "http://backend:8000", check_interval: int = 30):
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
        """Check if backend is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.backend_url}/api/health", follow_redirects=True)
                return response.status_code == 200
        except Exception as e:
            logger.debug(f"Backend health check failed: {e}")
            return False

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
            logger.warning("Backend unreachable, skipping sync")
            return {"synced": 0, "failed": 0, "remaining": await self._get_queue_count()}

        async with AsyncSessionLocal() as db:
            # Get unsync'd items in batches
            unsync_items = await self._get_unsync_items(db, limit=BATCH_SIZE)

            if not unsync_items:
                return {"synced": 0, "failed": 0, "remaining": 0}

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


# Global sync manager instance
sync_manager = SyncManager()
