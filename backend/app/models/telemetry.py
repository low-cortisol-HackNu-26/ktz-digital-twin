from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BIGINT, JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base


def _utcnow() -> datetime:
	return datetime.now(timezone.utc)


class Locomotive(Base):
	__tablename__ = "locomotives"

	id: Mapped[str] = mapped_column(String(64), primary_key=True)
	display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
	updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class TelemetryEventRecord(Base):
	__tablename__ = "telemetry_events"

	id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
	timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
	locomotive_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

	speed_kph: Mapped[float] = mapped_column(Float, nullable=False)
	target_speed_kph: Mapped[float | None] = mapped_column(Float, nullable=True)
	allowed_speed_kph: Mapped[float | None] = mapped_column(Float, nullable=True)
	acceleration: Mapped[float | None] = mapped_column(Float, nullable=True)
	traction_mode: Mapped[str] = mapped_column(String(16), nullable=False)
	tractive_effort_kn: Mapped[float | None] = mapped_column(Float, nullable=True)
	brake_pipe_pressure_bar: Mapped[float | None] = mapped_column(Float, nullable=True)
	brake_cylinder_pressure_bar: Mapped[float | None] = mapped_column(Float, nullable=True)
	pantograph_up: Mapped[bool] = mapped_column(nullable=False)
	catenary_voltage_kv: Mapped[float | None] = mapped_column(Float, nullable=True)
	traction_current_a: Mapped[float | None] = mapped_column(Float, nullable=True)
	traction_power_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
	regen_power_kw: Mapped[float | None] = mapped_column(Float, nullable=True)
	transformer_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
	converter_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
	traction_motor_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
	axle_bearing_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
	compressor_state: Mapped[str | None] = mapped_column(String(8), nullable=True)
	compressor_cycles_per_hour: Mapped[float | None] = mapped_column(Float, nullable=True)
	pneumatic_pressure_bar: Mapped[float | None] = mapped_column(Float, nullable=True)
	vibration_motor: Mapped[float | None] = mapped_column(Float, nullable=True)
	vibration_gearbox: Mapped[float | None] = mapped_column(Float, nullable=True)
	gps_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
	gps_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
	route_segment: Mapped[str | None] = mapped_column(String(128), nullable=True)
	gradient_permille: Mapped[float | None] = mapped_column(Float, nullable=True)
	train_mass_tons: Mapped[float | None] = mapped_column(Float, nullable=True)
	active_fault_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
	signal_quality: Mapped[float | None] = mapped_column(Float, nullable=True)
	data_quality: Mapped[float | None] = mapped_column(Float, nullable=True)
	ingestion_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
	source: Mapped[str | None] = mapped_column(String(64), nullable=True)
	schema_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0")


class CurrentSnapshot(Base):
	__tablename__ = "current_snapshots"

	locomotive_id: Mapped[str] = mapped_column(String(64), primary_key=True)
	payload: Mapped[dict] = mapped_column(JSON, nullable=False)
	event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
	updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class IngestionStat(Base):
	__tablename__ = "ingestion_stats"

	locomotive_id: Mapped[str] = mapped_column(String(64), primary_key=True)
	total_events: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	valid_events: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	invalid_events: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
	last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
	last_ingest_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

