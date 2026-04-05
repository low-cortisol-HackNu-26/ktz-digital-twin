"""Telemetry received from locomotives — dispatcher's own storage."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LocomotiveTelemetry(Base):
    """Raw telemetry event received from a locomotive via backup-queue."""

    __tablename__ = "locomotive_telemetry"
    __table_args__ = (
        Index("ix_loco_telemetry_loco_ts", "locomotive_id", "event_timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    locomotive_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    # Core fields stored as dedicated columns for quick queries
    speed_kph: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    route_segment: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Full event as JSON so nothing is lost
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)


class LocomotiveSnapshot(Base):
    """Latest known state per locomotive — upserted on every ingest."""

    __tablename__ = "locomotive_snapshots"

    locomotive_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    speed_kph: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    route_segment: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
