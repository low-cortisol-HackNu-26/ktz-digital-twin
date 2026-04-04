from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Inbound
# ---------------------------------------------------------------------------

class PositionReport(BaseModel):
    """Sent by the locomotive (or simulator) to report current GPS position."""
    locomotive_id: str = Field(..., min_length=1, max_length=64)
    lat: float = Field(..., ge=-90.0, le=90.0)
    lng: float = Field(..., ge=-180.0, le=180.0)
    speed: float = Field(default=0.0, ge=0.0)
    # Degrees clockwise from north; null if unknown
    heading: float | None = Field(default=None, ge=0.0, lt=360.0)


# ---------------------------------------------------------------------------
# Outbound — locomotive position
# ---------------------------------------------------------------------------

class LocomotivePositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    locomotive_id: str
    lat: float
    lng: float
    speed: float
    heading: float | None

    # Route assignment — null when the locomotive is off any known route
    route_id: str | None
    route_code: str | None
    route_name: str | None

    # Closest point on the route polyline
    snapped_lat: float | None
    snapped_lng: float | None
    # Raw-to-snapped distance in metres
    distance_to_route_m: float | None
    # 0–100 — percentage along the route (0 = origin, 100 = terminus)
    progress_pct: float | None

    updated_at: datetime


# ---------------------------------------------------------------------------
# Outbound — fleet snapshot
# ---------------------------------------------------------------------------

class FleetSnapshot(BaseModel):
    locomotives: list[LocomotivePositionOut]
    total: int
    # Locomotives not seen within this window are considered inactive
    active_window_minutes: int = 15


# ---------------------------------------------------------------------------
# Outbound — route GeoJSON
# ---------------------------------------------------------------------------

class RouteProperties(BaseModel):
    id: str
    code: str
    name: str
    total_length_km: float


class RouteFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: str
    geometry: dict[str, Any]   # {"type": "LineString", "coordinates": [[lng, lat], ...]}
    properties: RouteProperties


class RouteCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[RouteFeature]
