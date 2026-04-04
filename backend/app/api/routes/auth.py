from __future__ import annotations

import hashlib
import hmac
import secrets
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_current_user, get_current_user_optional, get_db
from ...auth.jwt import (
    decode_token,
    issue_access_token,
    issue_refresh_token,
    make_auth_response,
    make_driver_info,
    make_refresh_response,
    utcnow,
)
from ...models.user import AuthSession, DriverAccount
from ...schemas.auth import (
    DriverInfo,
    LoginRequest,
    LogoutResponse,
    OAuthTokenResponse,
    RegisterRequest,
    RefreshRequest,
    RefreshResponse,
    SessionResponse,
    TokenClaims,
)

router = APIRouter(prefix="/auth", tags=["auth"])

PBKDF2_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 390_000
SALT_BYTES = 16


def _pbkdf2_digest(password: str, salt: bytes, iterations: int) -> str:
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations)
    return dk.hex()


def _verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_s, salt_hex, digest_hex = password_hash.split(
            "$", 3)
        if algorithm != PBKDF2_ALGORITHM:
            return False
        iterations = int(iterations_s)
        salt = bytes.fromhex(salt_hex)
        computed = _pbkdf2_digest(plain_password, salt, iterations)
        return hmac.compare_digest(computed, digest_hex)
    except (ValueError, TypeError):
        return False


def _hash_password(plain_password: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    digest = _pbkdf2_digest(plain_password, salt, PBKDF2_ITERATIONS)
    return f"{PBKDF2_ALGORITHM}${PBKDF2_ITERATIONS}${salt.hex()}${digest}"


def _driver_info_from_user(user: DriverAccount) -> DriverInfo:
    return make_driver_info(
        user_id=user.id,
        company_id=user.company_id,
        name=user.name,
        role=user.role,
        locomotive_id=user.locomotive_id,
    )


async def _authenticate_user(uid: str, password: str, db: AsyncSession) -> DriverAccount:
    user_result = await db.execute(select(DriverAccount).where(DriverAccount.company_id == uid))
    user = user_result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid ID or password")

    if not _verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid ID or password")

    return user


@router.post("/register", response_model=DriverInfo, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenClaims | None = Depends(get_current_user_optional),
) -> DriverInfo:
    total_users_result = await db.execute(select(func.count()).select_from(DriverAccount))
    total_users = int(total_users_result.scalar_one() or 0)

    if total_users == 0:
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

    existing_result = await db.execute(
        select(DriverAccount).where(DriverAccount.company_id == payload.uid)
    )
    existing_user = existing_result.scalar_one_or_none()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    user = DriverAccount(
        company_id=payload.uid,
        password_hash=_hash_password(payload.password),
        name=payload.name,
        role=payload.role,
        locomotive_id=payload.locomotive_id,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return _driver_info_from_user(user)


@router.post("/token", response_model=OAuthTokenResponse)
async def token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> OAuthTokenResponse:
    user = await _authenticate_user(form_data.username, form_data.password, db)
    if user.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Swagger authorization is allowed only for Admin users",
        )

    session_id = str(uuid4())
    access_token, _, _ = issue_access_token(
        user_id=user.id,
        company_id=user.company_id,
        name=user.name,
        role=user.role,
        locomotive_id=user.locomotive_id,
        session_id=session_id,
    )
    _, refresh_expires_at, refresh_jti = issue_refresh_token(
        user_id=user.id,
        company_id=user.company_id,
        name=user.name,
        role=user.role,
        locomotive_id=user.locomotive_id,
        session_id=session_id,
    )

    db.add(
        AuthSession(
            id=session_id,
            user_id=user.id,
            refresh_jti=refresh_jti,
            expires_at=refresh_expires_at,
            last_used_at=utcnow(),
        )
    )
    user.last_login_at = utcnow()
    await db.flush()

    return OAuthTokenResponse(access_token=access_token, token_type="bearer")


@router.post("/card", response_model=SessionResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> SessionResponse:
    user = await _authenticate_user(payload.uid, payload.password, db)

    session_id = str(uuid4())
    access_token, access_expires_at, _ = issue_access_token(
        user_id=user.id,
        company_id=user.company_id,
        name=user.name,
        role=user.role,
        locomotive_id=user.locomotive_id,
        session_id=session_id,
    )
    refresh_token, refresh_expires_at, refresh_jti = issue_refresh_token(
        user_id=user.id,
        company_id=user.company_id,
        name=user.name,
        role=user.role,
        locomotive_id=user.locomotive_id,
        session_id=session_id,
    )

    db.add(
        AuthSession(
            id=session_id,
            user_id=user.id,
            refresh_jti=refresh_jti,
            expires_at=refresh_expires_at,
            last_used_at=utcnow(),
        )
    )
    user.last_login_at = utcnow()
    await db.flush()

    return make_auth_response(
        access_token=access_token,
        access_expires_at=access_expires_at,
        refresh_token=refresh_token,
        session_id=session_id,
        driver=_driver_info_from_user(user),
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)) -> RefreshResponse:
    claims = decode_token(payload.refresh_token, expected_type="refresh")

    session_result = await db.execute(select(AuthSession).where(AuthSession.id == claims.sid))
    auth_session = session_result.scalar_one_or_none()
    if auth_session is None or auth_session.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is no longer active")

    if auth_session.expires_at <= utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    if auth_session.refresh_jti != claims.jti:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Refresh token has been rotated")

    user_result = await db.execute(select(DriverAccount).where(DriverAccount.id == claims.sub))
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is disabled")

    access_token, access_expires_at, _ = issue_access_token(
        user_id=user.id,
        company_id=user.company_id,
        name=user.name,
        role=user.role,
        locomotive_id=user.locomotive_id,
        session_id=auth_session.id,
    )
    refresh_token, refresh_expires_at, refresh_jti = issue_refresh_token(
        user_id=user.id,
        company_id=user.company_id,
        name=user.name,
        role=user.role,
        locomotive_id=user.locomotive_id,
        session_id=auth_session.id,
    )

    auth_session.refresh_jti = refresh_jti
    auth_session.expires_at = refresh_expires_at
    auth_session.last_used_at = utcnow()
    await db.flush()

    return make_refresh_response(
        access_token=access_token,
        access_expires_at=access_expires_at,
        refresh_token=refresh_token,
        driver=_driver_info_from_user(user),
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    current_user: TokenClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LogoutResponse:
    session_result = await db.execute(select(AuthSession).where(AuthSession.id == current_user.sid))
    auth_session = session_result.scalar_one_or_none()
    if auth_session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is no longer active")

    auth_session.revoked_at = utcnow()
    auth_session.revoke_reason = "logout"
    auth_session.last_used_at = utcnow()
    await db.flush()
    return LogoutResponse(detail="Session revoked")


@router.get("/me", response_model=DriverInfo)
async def me(
    current_user: TokenClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DriverInfo:
    user_result = await db.execute(select(DriverAccount).where(DriverAccount.id == current_user.sub))
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is disabled")
    return _driver_info_from_user(user)
