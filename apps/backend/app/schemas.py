from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


TractionMode = Literal["traction", "coast", "braking", "regen"]
CompressorState = Literal["on", "off"]


class TelemetryEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    locomotive_id: str = Field(min_length=3, max_length=64)
    speed_kph: float = Field(ge=0.0, le=260.0)
    target_speed_kph: float | None = Field(default=None, ge=0.0, le=260.0)
    allowed_speed_kph: float | None = Field(default=None, ge=0.0, le=260.0)
    acceleration: float | None = Field(default=None, ge=-5.0, le=5.0)
    traction_mode: TractionMode
    tractive_effort_kn: float | None = Field(default=None, ge=-500.0, le=800.0)
    brake_pipe_pressure_bar: float | None = Field(default=None, ge=0.0, le=16.0)
    brake_cylinder_pressure_bar: float | None = Field(default=None, ge=0.0, le=16.0)
    pantograph_up: bool
    catenary_voltage_kv: float | None = Field(default=None, ge=0.0, le=35.0)
    traction_current_a: float | None = Field(default=None, ge=-5000.0, le=5000.0)
    traction_power_kw: float | None = Field(default=None, ge=-10000.0, le=12000.0)
    regen_power_kw: float | None = Field(default=None, ge=0.0, le=10000.0)
    transformer_temp_c: float | None = Field(default=None, ge=-40.0, le=220.0)
    converter_temp_c: float | None = Field(default=None, ge=-40.0, le=220.0)
    traction_motor_temp_c: float | None = Field(default=None, ge=-40.0, le=260.0)
    axle_bearing_temp_c: float | None = Field(default=None, ge=-40.0, le=220.0)
    compressor_state: CompressorState | None = None
    compressor_cycles_per_hour: float | None = Field(default=None, ge=0.0, le=600.0)
    pneumatic_pressure_bar: float | None = Field(default=None, ge=0.0, le=16.0)
    vibration_motor: float | None = Field(default=None, ge=0.0, le=60.0)
    vibration_gearbox: float | None = Field(default=None, ge=0.0, le=60.0)
    gps_lat: float | None = Field(default=None, ge=-90.0, le=90.0)
    gps_lon: float | None = Field(default=None, ge=-180.0, le=180.0)
    route_segment: str | None = Field(default=None, min_length=1, max_length=128)
    gradient_permille: float | None = Field(default=None, ge=-80.0, le=80.0)
    train_mass_tons: float | None = Field(default=None, ge=100.0, le=15000.0)
    active_fault_codes: list[str] = Field(default_factory=list, max_length=32)
    signal_quality: float | None = Field(default=None, ge=0.0, le=1.0)
    data_quality: float | None = Field(default=None, ge=0.0, le=1.0)

    ingestion_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = Field(default="simulator", min_length=1, max_length=64)
    schema_version: str = Field(default="1.0.0", min_length=1, max_length=32)

    @model_validator(mode="after")
    def ensure_timezone_and_codes(self) -> "TelemetryEvent":
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must include timezone")

        cleaned_codes = []
        for code in self.active_fault_codes:
            c = code.strip().upper()
            if not c:
                continue
            if len(c) > 32:
                raise ValueError("active_fault_codes items must be <= 32 chars")
            cleaned_codes.append(c)
        self.active_fault_codes = list(dict.fromkeys(cleaned_codes))

        if self.traction_mode == "regen" and self.regen_power_kw is None:
            raise ValueError("regen_power_kw is required when traction_mode=regen")
        if self.traction_mode == "traction" and self.traction_power_kw is None:
            raise ValueError("traction_power_kw is required when traction_mode=traction")
        return self


class IngestResult(BaseModel):
    accepted: int
    invalid: int
    dropped: int
    errors: list[dict]


PRIORITY_METRICS = [
    "speed_kph",
    "allowed_speed_kph",
    "traction_mode",
    "tractive_effort_kn",
    "brake_pipe_pressure_bar",
    "catenary_voltage_kv",
    "traction_current_a",
    "traction_power_kw",
    "regen_power_kw",
    "traction_motor_temp_c",
    "converter_temp_c",
    "transformer_temp_c",
    "axle_bearing_temp_c",
    "vibration_gearbox",
    "pneumatic_pressure_bar",
    "active_fault_codes",
    "gps_lat",
    "gps_lon",
    "route_segment",
    "signal_quality",
    "data_quality",
]
