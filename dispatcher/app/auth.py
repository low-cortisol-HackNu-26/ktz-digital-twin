"""Authentication utilities for dispatcher — fully compatible with backend JWT format."""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import AuthSession, DriverAccount

logger = logging.getLogger(__name__)

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production-min-32-chars!!")
JWT_ALGORITHM = "HS256"
TOKEN_LIFETIME_HOURS = int(os.getenv("TOKEN_LIFETIME_HOURS", "8"))
REFRESH_TOKEN_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", "7"))

PBKDF2_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 390_000
SALT_BYTES = 16

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


# ---------------------------------------------------------------------------
# Token claims
# ---------------------------------------------------------------------------

class TokenClaims(BaseModel):
    sub: str
    company_id: str
    name: str
    role: str
    locomotive_id: str | None = None
    sid: str
    jti: str
    token_type: Literal["access", "refresh"]
    iat: int
    exp: int


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"{PBKDF2_ALGORITHM}${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed.startswith("pbkdf2_sha256$"):
        return False
    try:
        _, iterations_s, salt_hex, digest_hex = hashed.split("$", 3)
        dk = hashlib.pbkdf2_hmac(
            "sha256", plain.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations_s)
        )
        return hmac.compare_digest(dk.hex(), digest_hex)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Token issuance
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _build_token(
    *,
    user_id: str,
    company_id: str,
    name: str,
    role: str,
    locomotive_id: str | None,
    session_id: str,
    token_type: str,
    lifetime: timedelta,
) -> tuple[str, datetime, str]:
    issued_at = _utcnow()
    expires_at = issued_at + lifetime
    jti = str(uuid4())
    payload = {
        "sub": user_id,
        "company_id": company_id,
        "name": name,
        "role": role,
        "locomotive_id": locomotive_id,
        "sid": session_id,
        "jti": jti,
        "token_type": token_type,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, expires_at, jti


def issue_access_token(
    *, user_id: str, company_id: str, name: str, role: str,
    locomotive_id: str | None, session_id: str,
) -> tuple[str, datetime, str]:
    return _build_token(
        user_id=user_id, company_id=company_id, name=name, role=role,
        locomotive_id=locomotive_id, session_id=session_id,
        token_type="access", lifetime=timedelta(hours=TOKEN_LIFETIME_HOURS),
    )


def issue_refresh_token(
    *, user_id: str, company_id: str, name: str, role: str,
    locomotive_id: str | None, session_id: str,
) -> tuple[str, datetime, str]:
    return _build_token(
        user_id=user_id, company_id=company_id, name=name, role=role,
        locomotive_id=locomotive_id, session_id=session_id,
        token_type="refresh", lifetime=timedelta(days=REFRESH_TOKEN_DAYS),
    )


def decode_token(token: str, *, expected_type: str | None = None) -> TokenClaims:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    claims = TokenClaims.model_validate(payload)
    if expected_type is not None and claims.token_type != expected_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    return claims


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> TokenClaims:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    claims = decode_token(token, expected_type="access")

    session_result = await db.execute(select(AuthSession).where(AuthSession.id == claims.sid))
    auth_session = session_result.scalar_one_or_none()
    if auth_session is None or auth_session.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is no longer active")

    if auth_session.expires_at <= _utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    user_result = await db.execute(select(DriverAccount).where(DriverAccount.id == claims.sub))
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is disabled")

    auth_session.last_used_at = _utcnow()
    return claims


async def get_current_user_optional(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> TokenClaims | None:
    if not token:
        return None
    return await get_current_user(token=token, db=db)


def require_role(*roles: str):
    async def dependency(current_user: TokenClaims = Depends(get_current_user)) -> TokenClaims:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user
    return dependency
