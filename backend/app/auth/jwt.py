from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from jose import JWTError, jwt

from ..config import settings
from ..schemas.auth import DriverInfo, RefreshResponse, SessionResponse, TokenClaims

ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_unix_ms(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


def _encode_claims(claims: dict[str, object]) -> str:
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=ALGORITHM)


def _decode_claims(token: str) -> dict[str, object]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


def _build_claims(
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
    issued_at = utcnow()
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
    return _encode_claims(payload), expires_at, jti


def issue_access_token(
    *,
    user_id: str,
    company_id: str,
    name: str,
    role: str,
    locomotive_id: str | None,
    session_id: str,
) -> tuple[str, datetime, str]:
    return _build_claims(
        user_id=user_id,
        company_id=company_id,
        name=name,
        role=role,
        locomotive_id=locomotive_id,
        session_id=session_id,
        token_type=ACCESS_TOKEN_TYPE,
        lifetime=timedelta(hours=settings.TOKEN_LIFETIME_HOURS),
    )


def issue_refresh_token(
    *,
    user_id: str,
    company_id: str,
    name: str,
    role: str,
    locomotive_id: str | None,
    session_id: str,
) -> tuple[str, datetime, str]:
    return _build_claims(
        user_id=user_id,
        company_id=company_id,
        name=name,
        role=role,
        locomotive_id=locomotive_id,
        session_id=session_id,
        token_type=REFRESH_TOKEN_TYPE,
        lifetime=timedelta(days=settings.REFRESH_TOKEN_DAYS),
    )


def decode_token(token: str, *, expected_type: str | None = None) -> TokenClaims:
    payload = _decode_claims(token)
    claims = TokenClaims.model_validate(payload)
    if expected_type is not None and claims.token_type != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    return claims


def make_driver_info(*, user_id: str, company_id: str, name: str, role: str, locomotive_id: str | None) -> DriverInfo:
    return DriverInfo(
        id=user_id,
        company_id=company_id,
        name=name,
        role=role,
        locomotive_id=locomotive_id,
    )


def make_auth_response(
    *,
    access_token: str,
    access_expires_at: datetime,
    refresh_token: str,
    session_id: str,
    driver: DriverInfo,
) -> SessionResponse:
    return SessionResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=to_unix_ms(access_expires_at),
        session_id=session_id,
        driver=driver,
    )


def make_refresh_response(
    *,
    access_token: str,
    access_expires_at: datetime,
    refresh_token: str,
    driver: DriverInfo,
) -> RefreshResponse:
    return RefreshResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=to_unix_ms(access_expires_at),
        driver=driver,
    )
