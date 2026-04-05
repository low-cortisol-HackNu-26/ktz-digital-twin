"""Auth endpoints — register, login, refresh, logout, me."""

from __future__ import annotations

import asyncio
import logging
import os
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    TokenClaims,
    _utcnow,
    decode_token,
    get_current_user,
    get_current_user_optional,
    hash_password,
    issue_access_token,
    issue_refresh_token,
    verify_password,
)
from app.database import get_db
from app.models.user import AuthSession, DriverAccount
from app.schemas import (
    DriverInfo,
    LoginRequest,
    LogoutResponse,
    OAuthTokenResponse,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    SessionResponse,
)

_BACKUP_QUEUE_URL = os.getenv("BACKUP_QUEUE_URL", "http://localhost:8001")
_BACKEND_SYNC_URL = os.getenv("BACKEND_SYNC_URL", "http://localhost:8000")
_SYNC_SECRET = os.getenv("SYNC_SECRET", "internal-sync-secret")

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


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


def _driver_info(user: DriverAccount) -> DriverInfo:
    return DriverInfo(
        id=user.id,
        company_id=user.company_id,
        name=user.name,
        role=user.role,
        locomotive_id=user.locomotive_id,
    )


async def _authenticate(uid: str, password: str, db: AsyncSession) -> DriverAccount:
    result = await db.execute(select(DriverAccount).where(DriverAccount.company_id == uid))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid ID or password")
    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid ID or password")
    return user


@router.post("/register", response_model=DriverInfo, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenClaims | None = Depends(get_current_user_optional),
) -> DriverInfo:
    """
    Register a new operator.

    - First ever user must have role **Admin** (no auth required).
    - All subsequent registrations require an **Admin** bearer token.
    """
    count_result = await db.execute(select(func.count()).select_from(DriverAccount))
    total = int(count_result.scalar_one() or 0)

    if total == 0:
        if payload.role != "Admin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The first registered user must have Admin role",
            )
    else:
        if current_user is None or current_user.role != "Admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Admin users can register new accounts",
            )

    existing = await db.execute(select(DriverAccount).where(DriverAccount.company_id == payload.uid))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    user = DriverAccount(
        company_id=payload.uid,
        password_hash=hash_password(payload.password),
        name=payload.name,
        role=payload.role,
        locomotive_id=payload.locomotive_id,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    logger.info(f"User registered: {payload.uid} (role: {payload.role})")
    asyncio.create_task(_queue_user_sync(user))
    return _driver_info(user)


@router.post("/token", response_model=OAuthTokenResponse, summary="Swagger OAuth2 login (Admin only)")
async def oauth2_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> OAuthTokenResponse:
    """OAuth2 password flow for Swagger UI — Admin users only."""
    user = await _authenticate(form_data.username, form_data.password, db)
    if user.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Swagger authorization is allowed only for Admin users",
        )
    session_id = str(uuid4())
    access_token, _, _ = issue_access_token(
        user_id=user.id, company_id=user.company_id, name=user.name,
        role=user.role, locomotive_id=user.locomotive_id, session_id=session_id,
    )
    _, refresh_expires_at, refresh_jti = issue_refresh_token(
        user_id=user.id, company_id=user.company_id, name=user.name,
        role=user.role, locomotive_id=user.locomotive_id, session_id=session_id,
    )
    db.add(AuthSession(
        id=session_id, user_id=user.id, refresh_jti=refresh_jti,
        expires_at=refresh_expires_at, last_used_at=_utcnow(),
    ))
    user.last_login_at = _utcnow()
    await db.flush()
    return OAuthTokenResponse(access_token=access_token)


@router.post("/card", response_model=SessionResponse, summary="Driver card / password login")
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """Authenticate with company ID + password and receive access + refresh tokens."""
    user = await _authenticate(payload.uid, payload.password, db)

    session_id = str(uuid4())
    access_token, access_expires_at, _ = issue_access_token(
        user_id=user.id, company_id=user.company_id, name=user.name,
        role=user.role, locomotive_id=user.locomotive_id, session_id=session_id,
    )
    refresh_token, refresh_expires_at, refresh_jti = issue_refresh_token(
        user_id=user.id, company_id=user.company_id, name=user.name,
        role=user.role, locomotive_id=user.locomotive_id, session_id=session_id,
    )
    db.add(AuthSession(
        id=session_id, user_id=user.id, refresh_jti=refresh_jti,
        expires_at=refresh_expires_at, last_used_at=_utcnow(),
    ))
    user.last_login_at = _utcnow()
    await db.flush()

    logger.info(f"Login: {user.company_id} (role: {user.role})")
    return SessionResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=int(access_expires_at.timestamp() * 1000),
        session_id=session_id,
        driver=_driver_info(user),
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> RefreshResponse:
    """Rotate refresh token and issue a new access token."""
    claims = decode_token(payload.refresh_token, expected_type="refresh")

    session_result = await db.execute(select(AuthSession).where(AuthSession.id == claims.sid))
    auth_session = session_result.scalar_one_or_none()
    if auth_session is None or auth_session.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is no longer active")
    if auth_session.expires_at <= _utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    if auth_session.refresh_jti != claims.jti:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has been rotated")

    user_result = await db.execute(select(DriverAccount).where(DriverAccount.id == claims.sub))
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is disabled")

    access_token, access_expires_at, _ = issue_access_token(
        user_id=user.id, company_id=user.company_id, name=user.name,
        role=user.role, locomotive_id=user.locomotive_id, session_id=auth_session.id,
    )
    refresh_token, refresh_expires_at, refresh_jti = issue_refresh_token(
        user_id=user.id, company_id=user.company_id, name=user.name,
        role=user.role, locomotive_id=user.locomotive_id, session_id=auth_session.id,
    )
    auth_session.refresh_jti = refresh_jti
    auth_session.expires_at = refresh_expires_at
    auth_session.last_used_at = _utcnow()
    await db.flush()

    return RefreshResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=int(access_expires_at.timestamp() * 1000),
        driver=_driver_info(user),
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    current_user: TokenClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LogoutResponse:
    """Revoke current session."""
    session_result = await db.execute(select(AuthSession).where(AuthSession.id == current_user.sid))
    auth_session = session_result.scalar_one_or_none()
    if auth_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session not found")
    auth_session.revoked_at = _utcnow()
    auth_session.revoke_reason = "logout"
    auth_session.last_used_at = _utcnow()
    await db.flush()
    logger.info(f"Logout: {current_user.company_id}")
    return LogoutResponse(detail="Session revoked")


@router.get("/me", response_model=DriverInfo)
async def me(
    current_user: TokenClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DriverInfo:
    """Return profile of the currently authenticated user."""
    result = await db.execute(select(DriverAccount).where(DriverAccount.id == current_user.sub))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is disabled")
    return _driver_info(user)
