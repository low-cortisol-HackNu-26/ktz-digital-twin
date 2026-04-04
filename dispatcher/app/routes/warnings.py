"""Warning/alert management endpoints."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import TokenClaims, get_current_user, require_role
from app.database import get_db, get_redis
from app.models.alert import LocomotiveWarning
from app.models.telemetry import CurrentSnapshot
from app.schemas import (
    ListWarningsResponse,
    ManualWarningCreateRequest,
    ManualWarningCreateResponse,
    WarningResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/warnings", tags=["warnings"])

TELEMETRY_CHANNEL = "telemetry.live"

_dispatcher_or_admin = require_role("Dispatcher", "Admin")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_active_warnings(db: AsyncSession, locomotive_id: str) -> list[LocomotiveWarning]:
    now = _utcnow()
    result = await db.execute(
        select(LocomotiveWarning).where(
            and_(
                LocomotiveWarning.locomotive_id == locomotive_id,
                LocomotiveWarning.active == True,
                (LocomotiveWarning.expires_at == None) | (LocomotiveWarning.expires_at > now),
            )
        )
    )
    return result.scalars().all()


async def _refresh_and_publish(db: AsyncSession, locomotive_id: str) -> None:
    """Re-read snapshot, attach current active warnings, push to Redis."""
    snapshot_result = await db.execute(
        select(CurrentSnapshot).where(CurrentSnapshot.locomotive_id == locomotive_id)
    )
    snapshot = snapshot_result.scalar_one_or_none()
    if snapshot is None:
        return

    warnings = await _get_active_warnings(db, locomotive_id)
    payload = dict(snapshot.payload)
    payload["active_warnings"] = [
        {
            "warning_id": w.warning_id,
            "locomotive_id": w.locomotive_id,
            "rule_id": w.rule_id,
            "source": w.source,
            "target_type": w.target_type,
            "target_id": w.target_id,
            "severity": w.severity,
            "title": w.title,
            "message": w.message,
            "recommended_action": w.recommended_action,
            "created_by": w.created_by,
            "metadata": w.warning_metadata,
            "expires_at": w.expires_at.isoformat() if w.expires_at else None,
            "active": w.active,
            "first_seen_at": w.first_seen_at.isoformat(),
            "last_seen_at": w.last_seen_at.isoformat(),
        }
        for w in warnings
    ]
    snapshot.payload = payload
    snapshot.updated_at = _utcnow()

    redis = await get_redis()
    if redis is not None:
        try:
            await redis.publish(TELEMETRY_CHANNEL, json.dumps(payload, ensure_ascii=True, default=str))
        except Exception as exc:
            logger.warning(f"Redis publish failed for {locomotive_id}: {exc}")


async def _locomotives_on_segment(db: AsyncSession, route_segment: str) -> list[str]:
    rows = (await db.execute(select(CurrentSnapshot))).scalars().all()
    result: list[str] = []
    for row in rows:
        if str(row.payload.get("route_segment") or "") == route_segment:
            result.append(row.locomotive_id)
    return sorted(set(result))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=ManualWarningCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create manual warning",
)
async def create_warning(
    request: ManualWarningCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenClaims = Depends(get_current_user),
) -> ManualWarningCreateResponse:
    """
    Create a manual warning targeting a specific locomotive or a route segment.

    When `target_type` is `route_segment`, the warning is broadcast to all
    locomotives currently on that segment and the snapshot of each is re-published
    to the real-time Redis channel so connected frontends update immediately.
    """
    now = _utcnow()
    expires_at = now + timedelta(seconds=request.duration_seconds)
    warning_id = f"manual:{request.target_type}:{request.target_id}:{request.warning_type}:{uuid4().hex[:12]}"
    rule_id = f"manual_{request.warning_type}"

    created_by = request.created_by or current_user.company_id

    if request.target_type == "locomotive":
        affected_locomotives = [request.target_id]
        loco_id_for_record = request.target_id
    elif request.target_type == "route_segment":
        affected_locomotives = await _locomotives_on_segment(db, request.target_id)
        loco_id_for_record = f"route_segment:{request.target_id}"
    else:
        raise HTTPException(status_code=422, detail="Unsupported target_type")

    warning = LocomotiveWarning(
        warning_id=warning_id,
        locomotive_id=loco_id_for_record,
        rule_id=rule_id,
        source=request.source,
        target_type=request.target_type,
        target_id=request.target_id,
        severity=request.severity,
        title=request.title,
        message=request.message,
        recommended_action=request.recommended_action,
        created_by=created_by,
        warning_metadata=request.metadata,
        expires_at=expires_at,
        active=True,
        first_seen_at=now,
        last_seen_at=now,
    )
    db.add(warning)
    await db.flush()

    for loco_id in affected_locomotives:
        await _refresh_and_publish(db, loco_id)

    await db.commit()

    logger.info(
        f"Manual warning created: {warning_id} by {created_by} "
        f"(affects {len(affected_locomotives)} locomotive(s))"
    )
    return ManualWarningCreateResponse(
        warning_id=warning_id,
        target_type=request.target_type,
        target_id=request.target_id,
        affected_locomotive_ids=affected_locomotives,
        expires_at=expires_at,
    )


@router.get(
    "/active",
    response_model=ListWarningsResponse,
    summary="Get all active warnings",
)
async def get_active_warnings(
    severity: str | None = Query(None, description="Filter by severity: info, warning, critical"),
    db: AsyncSession = Depends(get_db),
    _: TokenClaims = Depends(get_current_user),
) -> ListWarningsResponse:
    """Get all active, non-expired warnings across all locomotives."""
    now = _utcnow()
    query = select(LocomotiveWarning).where(
        and_(
            LocomotiveWarning.active == True,
            (LocomotiveWarning.expires_at == None) | (LocomotiveWarning.expires_at > now),
        )
    )
    if severity:
        query = query.where(LocomotiveWarning.severity == severity)

    result = await db.execute(query)
    warnings = result.scalars().all()
    return ListWarningsResponse(
        warnings=[WarningResponse.model_validate(w) for w in warnings],
        total_count=len(warnings),
    )


@router.get(
    "/locomotive/{locomotive_id}",
    response_model=ListWarningsResponse,
    summary="Get warnings for a locomotive",
)
async def get_locomotive_warnings(
    locomotive_id: str,
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    _: TokenClaims = Depends(get_current_user),
) -> ListWarningsResponse:
    query = select(LocomotiveWarning).where(LocomotiveWarning.locomotive_id == locomotive_id)
    if active_only:
        now = _utcnow()
        query = query.where(
            and_(
                LocomotiveWarning.active == True,
                (LocomotiveWarning.expires_at == None) | (LocomotiveWarning.expires_at > now),
            )
        )
    result = await db.execute(query)
    warnings = result.scalars().all()
    return ListWarningsResponse(
        warnings=[WarningResponse.model_validate(w) for w in warnings],
        total_count=len(warnings),
    )


@router.get(
    "/history",
    response_model=ListWarningsResponse,
    summary="Get warning history",
)
async def get_warning_history(
    locomotive_id: str | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: TokenClaims = Depends(get_current_user),
) -> ListWarningsResponse:
    query = select(LocomotiveWarning)
    if locomotive_id:
        query = query.where(LocomotiveWarning.locomotive_id == locomotive_id)
    if severity:
        query = query.where(LocomotiveWarning.severity == severity)

    count_result = await db.execute(query)
    total_count = len(count_result.scalars().all())

    result = await db.execute(
        query.order_by(LocomotiveWarning.last_seen_at.desc()).offset(skip).limit(limit)
    )
    warnings = result.scalars().all()
    return ListWarningsResponse(
        warnings=[WarningResponse.model_validate(w) for w in warnings],
        total_count=total_count,
    )


@router.put("/{warning_id}/deactivate", response_model=WarningResponse, summary="Deactivate warning")
async def deactivate_warning(
    warning_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenClaims = Depends(_dispatcher_or_admin),
) -> WarningResponse:
    result = await db.execute(
        select(LocomotiveWarning).where(LocomotiveWarning.warning_id == warning_id)
    )
    warning = result.scalar_one_or_none()
    if not warning:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Warning {warning_id} not found")

    warning.active = False
    warning.last_seen_at = _utcnow()
    await db.flush()

    # Republish snapshot so frontend removes the warning
    loco_id = warning.locomotive_id
    if not loco_id.startswith("route_segment:"):
        await _refresh_and_publish(db, loco_id)

    await db.commit()
    logger.info(f"Warning deactivated: {warning_id} by {current_user.company_id}")
    return WarningResponse.model_validate(warning)


@router.put("/{warning_id}/renew", response_model=WarningResponse, summary="Renew warning duration")
async def renew_warning(
    warning_id: str,
    expires_in_minutes: int = Query(60, ge=1, le=1440),
    db: AsyncSession = Depends(get_db),
    _: TokenClaims = Depends(_dispatcher_or_admin),
) -> WarningResponse:
    result = await db.execute(
        select(LocomotiveWarning).where(LocomotiveWarning.warning_id == warning_id)
    )
    warning = result.scalar_one_or_none()
    if not warning:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Warning {warning_id} not found")

    now = _utcnow()
    warning.expires_at = now + timedelta(minutes=expires_in_minutes)
    warning.active = True
    warning.last_seen_at = now
    await db.flush()

    loco_id = warning.locomotive_id
    if not loco_id.startswith("route_segment:"):
        await _refresh_and_publish(db, loco_id)

    await db.commit()
    logger.info(f"Warning renewed: {warning_id} (expires in {expires_in_minutes}m)")
    return WarningResponse.model_validate(warning)
