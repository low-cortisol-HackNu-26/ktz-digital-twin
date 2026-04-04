"""Route models — mirrors backend's routes / locomotive_positions tables."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Float, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    coordinates: Mapped[list] = mapped_column(JSON, nullable=False)
    total_length_km: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class LocomotivePosition(Base):
    __tablename__ = "locomotive_positions"

    locomotive_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    speed: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    heading: Mapped[float | None] = mapped_column(Float, nullable=True)
    route_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    route_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    route_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    snapped_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    snapped_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_to_route_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    progress_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
