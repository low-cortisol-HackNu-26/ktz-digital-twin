from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Float, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Route(Base):
    """A named railway corridor stored as a GeoJSON-ordered coordinate list."""

    __tablename__ = "routes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    # Short machine-readable code, e.g. "ALA-NUR"
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    # [[lng, lat], ...] — GeoJSON axis order (longitude first)
    coordinates: Mapped[list] = mapped_column(JSON, nullable=False)
    total_length_km: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class LocomotivePosition(Base):
    """
    One row per locomotive — upserted each time the locomotive reports its GPS.
    Stores the raw position AND the result of snapping it to the nearest route.
    """

    __tablename__ = "locomotive_positions"

    locomotive_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # Raw GPS from the locomotive
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    speed: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    heading: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Route assignment (null if no route is within snap threshold)
    route_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    route_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    route_name: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # Snapped point on the route polyline
    snapped_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    snapped_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Metres from raw GPS to the snapped point
    distance_to_route_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 0–100: how far along the route (0 = start, 100 = end)
    progress_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
