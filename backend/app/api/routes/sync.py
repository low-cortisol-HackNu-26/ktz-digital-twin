"""Internal service-to-service sync endpoints."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_db
from ...models.route import Route
from ...models.user import DriverAccount

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sync", tags=["internal-sync"])

_SYNC_SECRET = os.getenv("SYNC_SECRET", "internal-sync-secret")


def _verify_sync_secret(x_sync_secret: Optional[str] = Header(None, alias="X-Sync-Secret")) -> None:
    if not x_sync_secret or x_sync_secret != _SYNC_SECRET:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid sync secret")


class UserSyncPayload(BaseModel):
    id: str
    company_id: str
    password_hash: str
    name: str
    role: str
    locomotive_id: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None


@router.post(
    "/users",
    status_code=status.HTTP_200_OK,
    summary="Upsert a user synced from dispatcher",
    dependencies=[Depends(_verify_sync_secret)],
)
async def sync_user(
    payload: UserSyncPayload,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Upsert a user record synced from the dispatcher.
    Called by dispatcher via backup-queue (store-and-forward) whenever
    a user is created, updated, or deactivated on the dispatcher side.
    """
    result = await db.execute(
        select(DriverAccount).where(DriverAccount.id == payload.id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.company_id = payload.company_id
        existing.password_hash = payload.password_hash
        existing.name = payload.name
        existing.role = payload.role
        existing.locomotive_id = payload.locomotive_id
        existing.is_active = payload.is_active
        action = "updated"
    else:
        user = DriverAccount(
            id=payload.id,
            company_id=payload.company_id,
            password_hash=payload.password_hash,
            name=payload.name,
            role=payload.role,
            locomotive_id=payload.locomotive_id,
            is_active=payload.is_active,
        )
        if payload.created_at:
            user.created_at = payload.created_at
        db.add(user)
        action = "created"

    await db.commit()
    logger.info(f"User sync [{action}]: {payload.company_id} (id={payload.id})")
    return {"action": action, "id": payload.id, "company_id": payload.company_id}


@router.get(
    "/routes",
    status_code=status.HTTP_200_OK,
    summary="Export railway routes for dispatcher mirror DB",
    dependencies=[Depends(_verify_sync_secret)],
)
async def sync_export_routes(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Returns all routes so the dispatcher service can draw fleet maps locally."""
    rows = (await db.execute(select(Route))).scalars().all()
    return {
        "routes": [
            {
                "id": r.id,
                "code": r.code,
                "name": r.name,
                "coordinates": r.coordinates,
                "total_length_km": float(r.total_length_km or 0.0),
            }
            for r in rows
        ]
    }
