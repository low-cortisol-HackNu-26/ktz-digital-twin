from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

DEFAULT_INITIAL_STATE: dict[str, Any] = {
	"speed_kph": 0.0,
	"target_speed_kph": 0.0,
	"allowed_speed_kph": 80.0,
	"traction_type": "electric",
	# Demo abstraction for electric locomotive resources.
	"fuel_level_percent": 88.0,
	"fuel_consumption_lph": None,
	"energy_consumption_kwh": 0.0,
	"acceleration": 0.0,
	"traction_mode": "coast",
	"tractive_effort_kn": 0.0,
	"brake_pipe_pressure_bar": 5.0,
	"brake_cylinder_pressure_bar": 0.0,
	"brakes_temperature_c": 38.0,
	"pantograph_up": True,
	"catenary_voltage_kv": 25.0,
	"traction_current_a": 0.0,
	"traction_power_kw": 0.0,
	"regen_power_kw": 0.0,
	"transformer_temp_c": 42.0,
	"converter_temp_c": 39.0,
	"traction_motor_temp_c": 45.0,
	"axle_bearing_temp_c": 36.0,
	"compressor_state": "off",
	"compressor_cycles_per_hour": 9.0,
	"pneumatic_pressure_bar": 7.5,
	"vibration_motor": 0.7,
	"vibration_gearbox": 0.6,
	"gps_lat": 43.2389,
	"gps_lon": 76.8897,
	"route_segment": "ALA-NUR:000",
	"track_condition": "normal",
	"weather_condition": "clear",
	"gradient_permille": 0.0,
	"train_mass_tons": 6_500.0,
	"active_fault_codes": [],
	"signal_quality": 0.98,
	"data_quality": 0.99,
	"load_mode": "normal",
	"burst_active": False,
	"burst_multiplier": 1,
	"source": "simulator",
	"schema_version": "1.0",
}


def build_packet(locomotive_id: str, state: dict[str, Any]) -> dict[str, Any]:
	payload = dict(state)
	payload["timestamp"] = datetime.now(timezone.utc).isoformat()
	payload["locomotive_id"] = locomotive_id
	return payload
