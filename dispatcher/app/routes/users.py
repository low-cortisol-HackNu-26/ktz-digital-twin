"""User management endpoints (Admin only)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response  # noqa: F401
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import TokenClaims, require_role
from app.database import get_db
from app.models.user import DriverAccount
from app.schemas import ListUsersResponse, UserInfo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/users", tags=["users"])

_admin_only = require_role("Admin")


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
    return Response(status_code=status.HTTP_204_NO_CONTENT)
