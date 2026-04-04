from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_current_user, get_db
from ...core.route_matcher import match_position
from ...models.route import LocomotivePosition, Route
from ...schemas.auth import TokenClaims
from ...schemas.map import (
    FleetSnapshot,
    LocomotivePositionOut,
    PositionReport,
    RouteCollection,
    RouteFeature,
    RouteProperties,
)

router = APIRouter(prefix="/map", tags=["map"])

_ACTIVE_WINDOW_MINUTES = 15


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Routes (railway lines)
# ---------------------------------------------------------------------------

@router.get("/routes", response_model=RouteCollection, summary="All railway routes as GeoJSON")
async def get_routes(
    db: AsyncSession = Depends(get_db),
    _: TokenClaims = Depends(get_current_user),
) -> RouteCollection:
    """Returns every stored railway route as a GeoJSON FeatureCollection."""
    rows = (await db.execute(select(Route))).scalars().all()
    return RouteCollection(
        features=[
            RouteFeature(
                id=r.id,
                geometry={"type": "LineString", "coordinates": r.coordinates},
                properties=RouteProperties(
                    id=r.id,
                    code=r.code,
                    name=r.name,
                    total_length_km=r.total_length_km,
                ),
            )
            for r in rows
        ]
    )


@router.get(
    "/routes/{route_id}",
    response_model=RouteFeature,
    summary="Single route as GeoJSON",
)
async def get_route(
    route_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenClaims = Depends(get_current_user),
) -> RouteFeature:
    row = (await db.execute(select(Route).where(Route.id == route_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
    return RouteFeature(
        id=row.id,
        geometry={"type": "LineString", "coordinates": row.coordinates},
        properties=RouteProperties(
            id=row.id, code=row.code, name=row.name, total_length_km=row.total_length_km
        ),
    )


# ---------------------------------------------------------------------------
# Fleet positions
# ---------------------------------------------------------------------------

@router.get(
    "/fleet",
    response_model=FleetSnapshot,
    summary="All active locomotive positions",
)
async def get_fleet(
    db: AsyncSession = Depends(get_db),
    _: TokenClaims = Depends(get_current_user),
) -> FleetSnapshot:
    """
    Returns all locomotives that sent a position update in the last 15 minutes.
    Each entry includes the snapped position on the route (if matched).
    """
    cutoff = _utcnow() - timedelta(minutes=_ACTIVE_WINDOW_MINUTES)
    rows = (
        await db.execute(
            select(LocomotivePosition).where(LocomotivePosition.updated_at >= cutoff)
        )
    ).scalars().all()

    return FleetSnapshot(
        locomotives=[LocomotivePositionOut.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.get(
    "/fleet/{locomotive_id}",
    response_model=LocomotivePositionOut,
    summary="Single locomotive position",
)
async def get_locomotive_position(
    locomotive_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenClaims = Depends(get_current_user),
) -> LocomotivePositionOut:
    row = (
        await db.execute(
            select(LocomotivePosition).where(
                LocomotivePosition.locomotive_id == locomotive_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Locomotive not found")
    return LocomotivePositionOut.model_validate(row)


@router.get(
    "/routes/{route_id}/fleet",
    response_model=FleetSnapshot,
    summary="Locomotives currently on a specific route",
)
async def get_route_fleet(
    route_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenClaims = Depends(get_current_user),
) -> FleetSnapshot:
    """
    Returns all active locomotives whose snapped position is on this route.
    Useful for the frontend to highlight sibling trains.
    """
    cutoff = _utcnow() - timedelta(minutes=_ACTIVE_WINDOW_MINUTES)
    rows = (
        await db.execute(
            select(LocomotivePosition).where(
                LocomotivePosition.route_id == route_id,
                LocomotivePosition.updated_at >= cutoff,
            )
        )
    ).scalars().all()

    return FleetSnapshot(
        locomotives=[LocomotivePositionOut.model_validate(r) for r in rows],
        total=len(rows),
    )


# ---------------------------------------------------------------------------
# Position ingestion
# ---------------------------------------------------------------------------

@router.post(
    "/position",
    response_model=LocomotivePositionOut,
    summary="Report locomotive GPS position",
)
async def report_position(
    payload: PositionReport,
    db: AsyncSession = Depends(get_db),
    _: TokenClaims = Depends(get_current_user),
) -> LocomotivePositionOut:
    """
    Accepts a raw GPS position from the locomotive or simulator.

    1. Loads all railway routes from the database.
    2. Snaps the position to the nearest route within 1 km.
    3. Upserts a single row in locomotive_positions (one row per locomotive).
    4. Returns the full position record including route assignment.
    """
    routes = (await db.execute(select(Route))).scalars().all()
    snap = match_position(payload.lat, payload.lng, routes)

    # Upsert: one row per locomotive_id
    existing = (
        await db.execute(
            select(LocomotivePosition).where(
                LocomotivePosition.locomotive_id == payload.locomotive_id
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        existing = LocomotivePosition(locomotive_id=payload.locomotive_id)
        db.add(existing)

    existing.lat = payload.lat
    existing.lng = payload.lng
    existing.speed = payload.speed
    existing.heading = payload.heading
    existing.updated_at = _utcnow()

    if snap is not None:
        existing.route_id = snap.route_id
        existing.route_code = snap.route_code
        existing.route_name = snap.route_name
        existing.snapped_lat = snap.snapped_lat
        existing.snapped_lng = snap.snapped_lng
        existing.distance_to_route_m = snap.distance_km * 1_000
        existing.progress_pct = snap.progress_pct
    else:
        # Locomotive is off all known routes — clear previous assignment
        existing.route_id = None
        existing.route_code = None
        existing.route_name = None
        existing.snapped_lat = None
        existing.snapped_lng = None
        existing.distance_to_route_m = None
        existing.progress_pct = None

    await db.flush()
    await db.refresh(existing)
    return LocomotivePositionOut.model_validate(existing)
