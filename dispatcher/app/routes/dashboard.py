"""Fleet and dashboard endpoints."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import TokenClaims, get_current_user, issue_access_token
from app.database import get_db
from app.models.alert import LocomotiveWarning
from app.models.route import LocomotivePosition, Route
from app.models.telemetry import Locomotive
from app.schemas import (
    DashboardMetrics,
    FleetStatusResponse,
    ListRoutesResponse,
    LocoStatusInfo,
    RouteInfo,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dispatcher", tags=["dispatcher"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/fleet", response_model=FleetStatusResponse, summary="Get fleet status")
async def get_fleet_status(
    db: AsyncSession = Depends(get_db),
    _: TokenClaims | None = Depends(lambda: None),  # DEBUG: Make optional
) -> FleetStatusResponse:
    """Get current status of all locomotives in the fleet."""
    try:
        loco_result = await db.execute(select(Locomotive))
        locomotives = loco_result.scalars().all()

        positions_result = await db.execute(select(LocomotivePosition))
        positions_map: dict[str, LocomotivePosition] = {
            p.locomotive_id: p for p in positions_result.scalars().all()
        }

        now = _utcnow()
        warnings_result = await db.execute(
            select(LocomotiveWarning).where(
                and_(
                    LocomotiveWarning.active == True,
                    (LocomotiveWarning.expires_at == None) | (LocomotiveWarning.expires_at > now),
                )
            )
        )
        warning_counts: dict[str, int] = {}
        for w in warnings_result.scalars().all():
            warning_counts[w.locomotive_id] = warning_counts.get(w.locomotive_id, 0) + 1

        fleet_list: list[LocoStatusInfo] = []
        online_count = 0

        for loco in locomotives:
            pos = positions_map.get(loco.id)
            is_online = False
            if pos and pos.updated_at:
                is_online = (now - pos.updated_at).total_seconds() < 300

            if is_online:
                online_count += 1

            fleet_list.append(LocoStatusInfo(
                locomotive_id=loco.id,
                lat=pos.lat if pos else 0.0,
                lng=pos.lng if pos else 0.0,
                speed_kph=pos.speed if pos else 0.0,
                heading=pos.heading if pos else None,
                route_code=pos.route_code if pos else None,
                route_name=pos.route_name if pos else None,
                is_online=is_online,
                active_warnings_count=warning_counts.get(loco.id, 0),
                last_updated=pos.updated_at if pos else now,
            ))

        return FleetStatusResponse(
            locomotives=fleet_list,
            total_locomotives=len(locomotives),
            locomotives_online=online_count,
            active_warnings_count=sum(warning_counts.values()),
        )
    except Exception as exc:
        logger.error(f"Error getting fleet status: {exc}")
        return FleetStatusResponse(locomotives=[], total_locomotives=0, locomotives_online=0, active_warnings_count=0)


@router.get("/debug/warnings", summary="DEBUG: Get all warnings (no auth)")
async def debug_warnings(
    db: AsyncSession = Depends(get_db),
):
    """Debug endpoint to check warnings in database."""
    try:
        result = await db.execute(select(LocomotiveWarning))
        warnings = result.scalars().all()
        return {
            "count": len(warnings),
            "warnings": [
                {
                    "warning_id": w.warning_id,
                    "locomotive_id": w.locomotive_id,
                    "severity": w.severity,
                    "active": w.active,
                    "title": w.title,
                    "first_seen_at": w.first_seen_at.isoformat() if w.first_seen_at else None,
                }
                for w in warnings[:20]
            ]
        }
    except Exception as exc:
        logger.error(f"Error in debug endpoint: {exc}")
        return {"error": str(exc)}


@router.get("/debug/token", summary="DEBUG: Get test token (no auth)")
async def debug_token(
    db: AsyncSession = Depends(get_db),
):
    """Debug endpoint to get a test token without session validation."""
    try:
        session_id = str(uuid4())
        token, expires_at, _ = issue_access_token(
            user_id="debug-test-user",
            company_id="TEST_COMPANY",
            name="Debug Test",
            role="Admin",
            locomotive_id=None,
            session_id=session_id,
        )
        
        return {"access_token": token, "token_type": "bearer"}
    except Exception as exc:
        logger.error(f"Error generating token: {exc}")
        import traceback
        traceback.print_exc()
        return {"error": str(exc)}


@router.get("/routes", response_model=ListRoutesResponse, summary="Get all routes")
async def get_routes(
    db: AsyncSession = Depends(get_db),
    _: TokenClaims = Depends(get_current_user),
) -> ListRoutesResponse:
    try:
        result = await db.execute(select(Route))
        routes = result.scalars().all()
        return ListRoutesResponse(
            routes=[RouteInfo(code=r.code, name=r.name, total_length_km=r.total_length_km) for r in routes],
            total_count=len(routes),
        )
    except Exception as exc:
        logger.error(f"Error getting routes: {exc}")
        return ListRoutesResponse(routes=[], total_count=0)


@router.get("/metrics", response_model=DashboardMetrics, summary="Get dashboard metrics")
async def get_dashboard_metrics(
    db: AsyncSession = Depends(get_db),
    _: TokenClaims = Depends(get_current_user),
) -> DashboardMetrics:
    try:
        loco_result = await db.execute(select(Locomotive))
        total_locos = len(loco_result.scalars().all())

        now = _utcnow()
        five_min_ago = now - timedelta(minutes=5)
        online_result = await db.execute(
            select(LocomotivePosition).where(LocomotivePosition.updated_at > five_min_ago)
        )
        online_locos = len(online_result.scalars().all())

        warnings_result = await db.execute(
            select(LocomotiveWarning).where(
                and_(
                    LocomotiveWarning.active == True,
                    (LocomotiveWarning.expires_at == None) | (LocomotiveWarning.expires_at > now),
                )
            )
        )
        all_warnings = warnings_result.scalars().all()
        critical_count = sum(1 for w in all_warnings if w.severity == "critical")

        positions_result = await db.execute(select(LocomotivePosition))
        all_positions = positions_result.scalars().all()
        avg_speed = sum(p.speed for p in all_positions) / len(all_positions) if all_positions else 0.0

        return DashboardMetrics(
            total_locomotives=total_locos,
            online_locomotives=online_locos,
            total_active_warnings=len(all_warnings),
            critical_warnings_count=critical_count,
            total_events_today=0,
            avg_speed_kph=avg_speed,
            system_uptime_seconds=0.0,
        )
    except Exception as exc:
        logger.error(f"Error getting dashboard metrics: {exc}")
        return DashboardMetrics(
            total_locomotives=0, online_locomotives=0, total_active_warnings=0,
            critical_warnings_count=0, total_events_today=0, avg_speed_kph=0.0,
            system_uptime_seconds=0.0,
        )


@router.get("/locomotive/{locomotive_id}", summary="Get locomotive details")
async def get_locomotive_details(
    locomotive_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenClaims = Depends(get_current_user),
) -> dict:
    try:
        loco_result = await db.execute(select(Locomotive).where(Locomotive.id == locomotive_id))
        loco = loco_result.scalar_one_or_none()
        if not loco:
            return {"error": "Locomotive not found"}

        pos_result = await db.execute(
            select(LocomotivePosition).where(LocomotivePosition.locomotive_id == locomotive_id)
        )
        pos = pos_result.scalar_one_or_none()

        now = _utcnow()
        warnings_result = await db.execute(
            select(LocomotiveWarning).where(
                and_(
                    LocomotiveWarning.locomotive_id == locomotive_id,
                    LocomotiveWarning.active == True,
                    (LocomotiveWarning.expires_at == None) | (LocomotiveWarning.expires_at > now),
                )
            )
        )
        warnings = warnings_result.scalars().all()

        is_online = bool(pos and (now - pos.updated_at).total_seconds() < 300)
        return {
            "locomotive_id": loco.id,
            "name": loco.display_name,
            "status": "online" if is_online else "offline",
            "current_position": {
                "lat": pos.lat if pos else None,
                "lng": pos.lng if pos else None,
                "speed_kph": pos.speed if pos else 0,
                "heading": pos.heading if pos else 0,
                "route_code": pos.route_code if pos else None,
                "route_name": pos.route_name if pos else None,
                "last_updated": pos.updated_at.isoformat() if pos else None,
            },
            "active_warnings_count": len(warnings),
            "warnings": [
                {
                    "warning_id": w.warning_id,
                    "rule_id": w.rule_id,
                    "severity": w.severity,
                    "title": w.title,
                    "message": w.message,
                    "created_by": w.created_by,
                    "expires_at": w.expires_at.isoformat() if w.expires_at else None,
                    "first_seen_at": w.first_seen_at.isoformat(),
                }
                for w in warnings
            ],
        }
    except Exception as exc:
        logger.error(f"Error getting locomotive details for {locomotive_id}: {exc}")
        return {"error": str(exc)}
