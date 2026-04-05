"""Telemetry ingest endpoint — receives live data from locomotives via backup-queue."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.telemetry import Locomotive
from app.models.route import LocomotivePosition
from app.models.telemetry_ingest import LocomotiveTelemetry, LocomotiveSnapshot

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ingest", tags=["ingest"])

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TelemetryIngestRequest(BaseModel):
    locomotive_id: str = Field(..., min_length=1, max_length=64)
    timestamp: datetime
    speed_kph: float | None = None
    gps_lat: float | None = None
    gps_lon: float | None = None
    route_segment: str | None = None

    class Config:
        extra = "allow"  # preserve all extra fields in payload


class IngestResponse(BaseModel):
    accepted: int
    rejected: int


@router.post(
    "/telemetry",
    response_model=IngestResponse,
    status_code=status.HTTP_200_OK,
    summary="Receive live telemetry from locomotive",
)
async def ingest_telemetry(
    body: list[dict[str, Any]] | dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    """
    Accepts telemetry events from the backup-queue (train side).

    Accepts a single event dict or a list of events (for bulk flush after reconnect).
    Stores every event in `locomotive_telemetry` and upserts `locomotive_snapshots`.
    """
    events = body if isinstance(body, list) else [body]
    accepted = rejected = 0

    for raw in events:
        try:
            loco_id = str(raw.get("locomotive_id", "")).strip()
            if not loco_id:
                rejected += 1
                continue

            ts_raw = raw.get("timestamp")
            if ts_raw is None:
                rejected += 1
                continue
            event_ts = datetime.fromisoformat(str(ts_raw)) if isinstance(ts_raw, str) else ts_raw

            speed = raw.get("speed_kph")
            lat = raw.get("gps_lat")
            lng = raw.get("gps_lon") or raw.get("gps_lng")
            segment = raw.get("route_segment")

            # Ensure locomotive exists in the locomotives table
            loco_check = await db.execute(
                select(Locomotive).where(Locomotive.id == loco_id)
            )
            if loco_check.scalar_one_or_none() is None:
                db.add(Locomotive(id=loco_id, display_name=loco_id))

            # Store event
            db.add(LocomotiveTelemetry(
                locomotive_id=loco_id,
                event_timestamp=event_ts,
                speed_kph=float(speed) if speed is not None else None,
                gps_lat=float(lat) if lat is not None else None,
                gps_lng=float(lng) if lng is not None else None,
                route_segment=str(segment) if segment else None,
                payload=raw,
            ))

            # Upsert position
            if lat is not None and lng is not None:
                pos_result = await db.execute(
                    select(LocomotivePosition).where(LocomotivePosition.locomotive_id == loco_id)
                )
                pos = pos_result.scalar_one_or_none()

                if pos is None:
                    db.add(LocomotivePosition(
                        locomotive_id=loco_id,
                        lat=float(lat),
                        lng=float(lng),
                        speed=float(speed) if speed is not None else 0.0,
                        heading=raw.get("heading"),
                        route_code=raw.get("route_code"),
                        route_name=raw.get("route_name"),
                        snapped_lat=raw.get("snapped_lat"),
                        snapped_lng=raw.get("snapped_lng"),
                        distance_to_route_m=raw.get("distance_to_route_m"),
                        progress_pct=raw.get("progress_pct"),
                    ))
                else:
                    pos.lat = float(lat)
                    pos.lng = float(lng)
                    pos.speed = float(speed) if speed is not None else 0.0
                    pos.heading = raw.get("heading")
                    pos.route_code = raw.get("route_code")
                    pos.route_name = raw.get("route_name")
                    pos.snapped_lat = raw.get("snapped_lat")
                    pos.snapped_lng = raw.get("snapped_lng")
                    pos.distance_to_route_m = raw.get("distance_to_route_m")
                    pos.progress_pct = raw.get("progress_pct")
                    pos.updated_at = _utcnow()

            # Upsert snapshot
            snap_result = await db.execute(
                select(LocomotiveSnapshot).where(LocomotiveSnapshot.locomotive_id == loco_id)
            )
            snap = snap_result.scalar_one_or_none()

            if snap is None:
                db.add(LocomotiveSnapshot(
                    locomotive_id=loco_id,
                    last_event_timestamp=event_ts,
                    speed_kph=float(speed) if speed is not None else None,
                    gps_lat=float(lat) if lat is not None else None,
                    gps_lng=float(lng) if lng is not None else None,
                    route_segment=str(segment) if segment else None,
                    payload=raw,
                ))
            elif event_ts >= snap.last_event_timestamp:
                snap.last_event_timestamp = event_ts
                snap.updated_at = _utcnow()
                snap.speed_kph = float(speed) if speed is not None else snap.speed_kph
                snap.gps_lat = float(lat) if lat is not None else snap.gps_lat
                snap.gps_lng = float(lng) if lng is not None else snap.gps_lng
                snap.route_segment = str(segment) if segment else snap.route_segment
                snap.payload = raw

            accepted += 1

        except Exception as exc:
            logger.warning(f"Rejected event: {exc} — {str(raw)[:120]}")
            rejected += 1

    if accepted:
        logger.info(f"Ingested {accepted} event(s) ({rejected} rejected)")

    return IngestResponse(accepted=accepted, rejected=rejected)
