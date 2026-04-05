"""User management endpoints (Admin only)."""

from __future__ import annotations

import asyncio
import logging
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response  # noqa: F401
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import TokenClaims, require_role
from app.database import get_db
from app.models.user import DriverAccount
from app.schemas import ListUsersResponse, UserInfo

_BACKUP_QUEUE_URL = os.getenv("BACKUP_QUEUE_URL", "http://localhost:8001")
_BACKEND_SYNC_URL = os.getenv("BACKEND_SYNC_URL", "http://localhost:8000")
_SYNC_SECRET = os.getenv("SYNC_SECRET", "internal-sync-secret")

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/users", tags=["users"])

_admin_only = require_role("Admin")


async def _queue_user_sync(user: DriverAccount) -> None:
    """Queue a user sync to the backend via backup-queue."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            payload = {
                "event_type": "user_sync",
                "endpoint": "/api/sync/users",
                "target_url": _BACKEND_SYNC_URL,
                "payload": {
                    "id": user.id,
                    "company_id": user.company_id,
                    "password_hash": user.password_hash,
                    "name": user.name,
                    "role": user.role,
                    "locomotive_id": user.locomotive_id,
                    "is_active": user.is_active,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                },
                "auth_token": _SYNC_SECRET,
            }
            await client.post(
                f"{_BACKUP_QUEUE_URL}/api/queue/dispatcher",
                json=payload,
            )
            logger.debug(f"Queued user sync: {user.company_id}")
    except Exception as e:
        logger.warning(f"Failed to queue user sync: {e}")


@router.get("", response_model=ListUsersResponse, summary="List all operators")
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: TokenClaims = Depends(_admin_only),
) -> ListUsersResponse:
    """Get paginated list of all registered operators."""
    count_result = await db.execute(select(func.count()).select_from(DriverAccount))
    total_count = int(count_result.scalar_one() or 0)

    result = await db.execute(select(DriverAccount).offset(skip).limit(limit))
    users = result.scalars().all()

    return ListUsersResponse(
        users=[UserInfo.model_validate(u) for u in users],
        total_count=total_count,
    )


@router.get("/{user_id}", response_model=UserInfo, summary="Get user details")
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenClaims = Depends(_admin_only),
) -> UserInfo:
    result = await db.execute(select(DriverAccount).where(DriverAccount.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found")
    return UserInfo.model_validate(user)


@router.put("/{user_id}/role", response_model=UserInfo, summary="Update user role")
async def update_user_role(
    user_id: str,
    new_role: str,
    db: AsyncSession = Depends(get_db),
    _: TokenClaims = Depends(_admin_only),
) -> UserInfo:
    if new_role not in ("Admin", "Dispatcher", "Machinist", "Operator"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")

    result = await db.execute(select(DriverAccount).where(DriverAccount.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found")

    user.role = new_role
    await db.commit()
    await db.refresh(user)
    logger.info(f"User role updated: {user.company_id} → {new_role}")
    asyncio.create_task(_queue_user_sync(user))
    return UserInfo.model_validate(user)


@router.put("/{user_id}/locomotive", response_model=UserInfo, summary="Assign locomotive to operator")
async def assign_locomotive(
    user_id: str,
    locomotive_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenClaims = Depends(_admin_only),
) -> UserInfo:
    result = await db.execute(select(DriverAccount).where(DriverAccount.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found")

    user.locomotive_id = locomotive_id
    await db.commit()
    await db.refresh(user)
    logger.info(f"Locomotive assigned: {user.company_id} → {locomotive_id}")
    asyncio.create_task(_queue_user_sync(user))
    return UserInfo.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Deactivate user", response_model=None)
async def deactivate_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenClaims = Depends(_admin_only),
) -> Response:
    result = await db.execute(select(DriverAccount).where(DriverAccount.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found")

    user.is_active = False
    await db.commit()
    logger.info(f"User deactivated: {user.company_id}")
    asyncio.create_task(_queue_user_sync(user))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
