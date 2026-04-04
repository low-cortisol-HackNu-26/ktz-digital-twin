"""
Inserts known locomotives into the DB at startup if they are missing.

The locomotive list is read from settings.KNOWN_LOCOMOTIVES (comma-separated).
This is idempotent: existing rows are never overwritten.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models.telemetry import Locomotive

logger = logging.getLogger(__name__)


async def seed_locomotives_if_missing(session: AsyncSession) -> None:
    loco_ids = [lid.strip() for lid in settings.KNOWN_LOCOMOTIVES.split(",") if lid.strip()]
    if not loco_ids:
        logger.info("loco_seeder: KNOWN_LOCOMOTIVES is empty, nothing to seed")
        return

    inserted = 0
    for loco_id in loco_ids:
        existing = (
            await session.execute(select(Locomotive).where(Locomotive.id == loco_id))
        ).scalar_one_or_none()
        if existing is None:
            session.add(Locomotive(id=loco_id, display_name=loco_id))
            inserted += 1

    if inserted:
        await session.commit()
        logger.info("loco_seeder: inserted %d locomotives", inserted)
    else:
        logger.info("loco_seeder: all locomotives already present")
