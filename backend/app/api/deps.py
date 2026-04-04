from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.jwt import decode_token
from ..db.session import get_session
from ..models.user import AuthSession, DriverAccount
from ..schemas.auth import TokenClaims

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> TokenClaims:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    claims = decode_token(token, expected_type="access")

    session_result = await db.execute(select(AuthSession).where(AuthSession.id == claims.sid))
    auth_session = session_result.scalar_one_or_none()
    if auth_session is None or auth_session.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is no longer active")

    if auth_session.expires_at <= _utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    user_result = await db.execute(select(DriverAccount).where(DriverAccount.id == claims.sub))
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is disabled")

    auth_session.last_used_at = _utcnow()
    return claims


async def get_current_user_optional(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> TokenClaims | None:
    if not token:
        return None
    return await get_current_user(token=token, db=db)


def require_role(*roles: str) -> Callable[[TokenClaims], TokenClaims]:
    async def dependency(current_user: TokenClaims = Depends(get_current_user)) -> TokenClaims:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user

    return dependency
