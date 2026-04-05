"""Background sync tasks — syncs data from backend to dispatcher."""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.alert import LocomotiveWarning

logger = logging.getLogger(__name__)

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
SYNC_SECRET = os.getenv("SYNC_SECRET", "")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso_datetime(iso_string: str | None) -> datetime | None:
    """Parse ISO 8601 datetime string to datetime object."""
    if not iso_string:
        return None
    try:
        return datetime.fromisoformat(str(iso_string))
    except (ValueError, TypeError):
        return None


async def sync_warnings_from_backend(db: AsyncSession) -> int:
    """Sync all warnings from backend to dispatcher.
    
    Returns: Number of warnings synced
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Fetch all active warnings from backend
            response = await client.get(
                f"{BACKEND_URL}/api/warnings/all",
                headers={"X-Sync-Secret": SYNC_SECRET},
            )
            response.raise_for_status()
            
            data = response.json()
            warnings_list = data.get("warnings", [])
            
            synced_count = 0
            
            for warn_data in warnings_list:
                warn_id = warn_data.get("warning_id")
                if not warn_id:
                    continue
                
                # Check if warning exists locally
                existing = await db.execute(
                    select(LocomotiveWarning).where(
                        LocomotiveWarning.warning_id == warn_id
                    )
                )
                existing_warn = existing.scalar_one_or_none()
                
                if existing_warn is None:
                    # Create new warning
                    db.add(LocomotiveWarning(
                        warning_id=warn_id,
                        locomotive_id=warn_data.get("locomotive_id"),
                        rule_id=warn_data.get("rule_id"),
                        source=warn_data.get("source", "system"),
                        target_type=warn_data.get("target_type", "locomotive"),
                        target_id=warn_data.get("target_id"),
                        severity=warn_data.get("severity"),
                        title=warn_data.get("title", ""),
                        message=warn_data.get("message", ""),
                        recommended_action=warn_data.get("recommended_action", ""),
                        created_by=warn_data.get("created_by"),
                        active=warn_data.get("active", False),
                        first_seen_at=_parse_iso_datetime(warn_data.get("first_seen_at")),
                        last_seen_at=_parse_iso_datetime(warn_data.get("last_seen_at")),
                        expires_at=_parse_iso_datetime(warn_data.get("expires_at")),
                    ))
                    synced_count += 1
                else:
                    # Update existing warning
                    existing_warn.severity = warn_data.get("severity")
                    existing_warn.title = warn_data.get("title", "")
                    existing_warn.message = warn_data.get("message", "")
                    existing_warn.recommended_action = warn_data.get("recommended_action", "")
                    existing_warn.active = warn_data.get("active", False)
                    existing_warn.last_seen_at = _parse_iso_datetime(warn_data.get("last_seen_at"))
                    existing_warn.expires_at = _parse_iso_datetime(warn_data.get("expires_at"))
                    synced_count += 1
            
            await db.commit()
            logger.info(f"Synced {synced_count} warnings from backend")
            return synced_count
            
    except Exception as exc:
        logger.error(f"Error syncing warnings from backend: {exc}")
        await db.rollback()
        return 0


async def start_background_sync():
    """Start background sync task."""
    logger.info("Starting background warning sync task...")
    
    while True:
        try:
            async for db in get_db():
                await sync_warnings_from_backend(db)
                break
        except Exception as exc:
            logger.error(f"Background sync task error: {exc}")
        
        # Sync every 30 seconds
        await asyncio.sleep(30)
