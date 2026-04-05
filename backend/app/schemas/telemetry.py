from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _utcnow() -> datetime:
	return datetime.now(timezone.utc)


class TelemetryEvent(BaseModel):
	model_config = ConfigDict(from_attributes=True, extra="ignore")

	timestamp: datetime
	locomotive_id: str = Field(..., min_length=1, max_length=64)
	traction_type: Literal["electric", "diesel", "fuel"] = "electric"
	speed_kph: float = Field(..., ge=0)
	target_speed_kph: float | None = Field(default=None, ge=0)
	allowed_speed_kph: float | None = Field(default=None, ge=0)
	fuel_level_percent: float | None = Field(default=None, ge=0, le=100)
	fuel_consumption_lph: float | None = Field(default=None, ge=0)
	energy_consumption_kwh: float | None = Field(default=None, ge=0)
	base_allowed_speed_kph: float | None = Field(default=None, ge=0)
	effective_allowed_speed_kph: float | None = Field(default=None, ge=0)
	acceleration: float | None = None
	traction_mode: Literal["traction", "coast", "braking", "regen"]
	tractive_effort_kn: float | None = None
	brake_pipe_pressure_bar: float | None = None
	brake_cylinder_pressure_bar: float | None = None
	brakes_temperature_c: float | None = None
	pressure_bar: float | None = None
	pantograph_up: bool
	catenary_voltage_kv: float | None = None
	voltage_kv: float | None = None
	traction_current_a: float | None = None
	current_a: float | None = None
	traction_power_kw: float | None = None
	regen_power_kw: float | None = None
	transformer_temp_c: float | None = None
	converter_temp_c: float | None = None
	traction_motor_temp_c: float | None = None
	engine_temperature_c: float | None = None
	axle_bearing_temp_c: float | None = None
	compressor_state: Literal["on", "off"] | None = None
	compressor_cycles_per_hour: float | None = Field(default=None, ge=0)
	pneumatic_pressure_bar: float | None = None
	vibration_motor: float | None = Field(default=None, ge=0)
	vibration_gearbox: float | None = Field(default=None, ge=0)
	gps_lat: float | None = None
	gps_lon: float | None = None
	route_segment: str | None = Field(default=None, max_length=128)
	track_condition: Literal["normal", "rough", "bad", "maintenance_zone"] | None = None
	weather_condition: Literal["clear", "rain", "snow", "fog", "wind"] | None = None
	route_progress_percent: float | None = Field(default=None, ge=0, le=100)
	distance_to_destination_km: float | None = Field(default=None, ge=0)
	eta_seconds: int | None = Field(default=None, ge=0)
	eta_timestamp: datetime | None = None
	gradient_permille: float | None = None
	train_mass_tons: float | None = Field(default=None, ge=0)
	active_fault_codes: list[str] = Field(default_factory=list)
	signal_quality: float | None = Field(default=None, ge=0, le=1)
	data_quality: float | None = Field(default=None, ge=0, le=1)
	ingestion_time: datetime | None = None
	source: str | None = Field(default=None, max_length=64)
	schema_version: str = Field(default="1.0", min_length=1, max_length=32)

	@field_validator("brake_pipe_pressure_bar", "brake_cylinder_pressure_bar", "pneumatic_pressure_bar", "pressure_bar")
	@classmethod
	def validate_pressure_ranges(cls, value: float | None) -> float | None:
		if value is None:
			return value
		if not 0 <= value <= 16:
			raise ValueError("pressure must be in range 0..16 bar")
		return value

	@field_validator(
		"transformer_temp_c",
		"converter_temp_c",
		"traction_motor_temp_c",
		"engine_temperature_c",
		"brakes_temperature_c",
		"axle_bearing_temp_c",
	)
	@classmethod
	def validate_temperature_ranges(cls, value: float | None) -> float | None:
		if value is None:
			return value
		if not -60 <= value <= 220:
			raise ValueError("temperature must be in range -60..220 C")
		return value

	@field_validator("catenary_voltage_kv", "voltage_kv")
	@classmethod
	def validate_voltage_range(cls, value: float | None) -> float | None:
		if value is None:
			return value
		if not 0 <= value <= 35:
			raise ValueError("catenary voltage must be in range 0..35 kV")
		return value

	@field_validator("traction_current_a", "current_a")
	@classmethod
	def validate_current_range(cls, value: float | None) -> float | None:
		if value is None:
			return value
		if not 0 <= value <= 5000:
			raise ValueError("current must be in range 0..5000 A")
		return value

	@model_validator(mode="after")
	def validate_gps_pair(self) -> "TelemetryEvent":
		if (self.gps_lat is None) != (self.gps_lon is None):
			raise ValueError("gps_lat and gps_lon must be provided together")
		if self.gps_lat is not None and not -90 <= self.gps_lat <= 90:
			raise ValueError("gps_lat must be in range -90..90")
		if self.gps_lon is not None and not -180 <= self.gps_lon <= 180:
			raise ValueError("gps_lon must be in range -180..180")
		return self


class TelemetryIngestRequest(BaseModel):
	events: list[TelemetryEvent] = Field(default_factory=list)


class InvalidEvent(BaseModel):
	index: int
	error: str


class TelemetryIngestResponse(BaseModel):
	accepted: int
	rejected: int
	invalid_items: list[InvalidEvent]


class ActiveWarningResponse(BaseModel):
	warning_id: str
	locomotive_id: str
	rule_id: str
	source: Literal["system", "dispatcher", "admin"]
	target_type: Literal["locomotive", "route_segment"]
	target_id: str
	severity: str
	title: str
	message: str
	recommended_action: str
	status: Literal["active", "cleared", "expired"]
	allowed_speed_kph_override: float | None = Field(default=None, ge=0)
	created_by: str | None = None
	metadata: dict | None = None
	expires_at: datetime | None = None
	cleared_at: datetime | None = None
	active: bool
	first_seen_at: datetime
	last_seen_at: datetime


class ManualWarningCreateRequest(BaseModel):
	target_type: Literal["locomotive", "route_segment"]
	target_id: str = Field(..., min_length=1, max_length=128)
	warning_type: Literal[
		"weather",
		"track",
		"maintenance_zone",
		"temporary_speed_limit",
		"manual_caution",
	]
	severity: Literal["info", "warning", "critical"]
	title: str = Field(..., min_length=1, max_length=128)
	message: str = Field(..., min_length=1)
	recommended_action: str = Field(..., min_length=1)
	duration_seconds: int = Field(..., ge=1, le=86400)
	source: Literal["dispatcher", "admin"]
	allowed_speed_kph_override: float | None = Field(default=None, ge=0)
	created_by: str | None = Field(default=None, max_length=128)
	metadata: dict | None = None


class ManualWarningCreateResponse(BaseModel):
	warning_id: str
	target_type: Literal["locomotive", "route_segment"]
	target_id: str
	affected_locomotive_ids: list[str]
	expires_at: datetime


class LocomotiveCurrentResponse(BaseModel):
	locomotive_id: str
	event: TelemetryEvent | None
	active_warnings: list[ActiveWarningResponse] = Field(default_factory=list)


class ReplayFrame(BaseModel):
	timestamp: datetime
	locomotive_id: str
	snapshot: dict
	active_warnings: list[ActiveWarningResponse] = Field(default_factory=list)


class ReplayResponse(BaseModel):
	locomotive_id: str
	from_ts: datetime = Field(..., alias="from")
	to_ts: datetime = Field(..., alias="to")
	telemetry_frames: list[ReplayFrame] = Field(default_factory=list)
	warnings: list[ActiveWarningResponse] = Field(default_factory=list)
	summary: dict | None = None


class SystemMetricsResponse(BaseModel):
	ingest_rate_per_sec: int
	valid_events_count: int
	invalid_events_count: int
	dropped_events_count: int
	db_write_latency_ms: float
	redis_publish_latency_ms: float
	ws_clients_count: int
	last_event_timestamp: str | None
	per_locomotive_last_seen: dict[str, str]


class IngestionStatsResponse(BaseModel):
	locomotive_id: str
	total_events: int
	valid_events: int
	invalid_events: int
	last_ingest_time: datetime

