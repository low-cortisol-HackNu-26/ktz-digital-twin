from __future__ import annotations

from typing import Any


# Scripted demo route: Almaty (A) -> Astana (B) through fixed waypoints.
_ROUTE_WAYPOINTS: list[tuple[float, float]] = [
	(43.2389, 76.8897),
	(44.8500, 75.2000),
	(46.4000, 74.3000),
	(48.0000, 73.2000),
	(49.7000, 72.1000),
	(51.1605, 71.4704),
]

# Route warning windows in normalized progress [0, 1].
_WARNING_SEGMENTS: list[tuple[float, float]] = [
	(0.32, 0.40),
	(0.70, 0.78),
]

_ACCEL_SEC = 3.0
_CRUISE_SEC = 54.0
_BRAKE_SEC = 6.0
_STOP_SEC = 9.0
_CRUISE_SPEED_KPH = 78.0
_WARNING_DURATION_SEC = 5.0
_WARNING_GAP_SEC = 3.0
_WARNING_START_SEC = 12.0
_DEMO_WARNING_SEQUENCE: list[str] = [
	"upcoming_bad_track",
	"high_vibration",
	"overspeed",
	"high_temperature",
	"low_signal_quality",
	"voltage_sag",
]


def _clamp01(value: float) -> float:
	return max(0.0, min(1.0, value))


def _speed_profile_kph(elapsed_sec: float) -> tuple[float, str]:
	if elapsed_sec < _ACCEL_SEC:
		return _CRUISE_SPEED_KPH * (elapsed_sec / _ACCEL_SEC), "traction"

	if elapsed_sec < _ACCEL_SEC + _CRUISE_SEC:
		return _CRUISE_SPEED_KPH, "coast"

	if elapsed_sec < _ACCEL_SEC + _CRUISE_SEC + _BRAKE_SEC:
		decel_t = elapsed_sec - (_ACCEL_SEC + _CRUISE_SEC)
		left = _clamp01(1.0 - decel_t / _BRAKE_SEC)
		return _CRUISE_SPEED_KPH * left, "braking"

	return 0.0, "regen"


def _distance_progress(elapsed_sec: float) -> float:
	move_total_sec = _ACCEL_SEC + _CRUISE_SEC + _BRAKE_SEC
	if elapsed_sec <= 0:
		return 0.0
	if elapsed_sec >= move_total_sec:
		return 1.0

	accel_area = 0.5 * _CRUISE_SPEED_KPH * _ACCEL_SEC
	cruise_area = _CRUISE_SPEED_KPH * _CRUISE_SEC
	brake_area = 0.5 * _CRUISE_SPEED_KPH * _BRAKE_SEC
	total_area = accel_area + cruise_area + brake_area

	if elapsed_sec < _ACCEL_SEC:
		covered = 0.5 * _CRUISE_SPEED_KPH * (elapsed_sec**2) / _ACCEL_SEC
		return _clamp01(covered / total_area)

	if elapsed_sec < _ACCEL_SEC + _CRUISE_SEC:
		cruise_t = elapsed_sec - _ACCEL_SEC
		covered = accel_area + _CRUISE_SPEED_KPH * cruise_t
		return _clamp01(covered / total_area)

	decel_t = elapsed_sec - (_ACCEL_SEC + _CRUISE_SEC)
	covered = accel_area + cruise_area + (_CRUISE_SPEED_KPH * decel_t - 0.5 * _CRUISE_SPEED_KPH * (decel_t**2) / _BRAKE_SEC)
	return _clamp01(covered / total_area)


def _interpolate_route(progress: float) -> tuple[float, float, int]:
	p = _clamp01(progress)
	segments = len(_ROUTE_WAYPOINTS) - 1
	if segments <= 0:
		lat, lon = _ROUTE_WAYPOINTS[0]
		return lat, lon, 0

	pos = p * segments
	idx = min(segments - 1, int(pos))
	frac = pos - idx

	lat_a, lon_a = _ROUTE_WAYPOINTS[idx]
	lat_b, lon_b = _ROUTE_WAYPOINTS[idx + 1]
	lat = lat_a + (lat_b - lat_a) * frac
	lon = lon_a + (lon_b - lon_a) * frac
	return lat, lon, idx


def _is_warning_segment(progress: float) -> bool:
	for start, end in _WARNING_SEGMENTS:
		if start <= progress <= end:
			return True
	return False


def _active_demo_warning(elapsed_sec: float) -> str | None:
	if elapsed_sec < _WARNING_START_SEC:
		return None

	time_from_start = elapsed_sec - _WARNING_START_SEC
	step_sec = _WARNING_DURATION_SEC + _WARNING_GAP_SEC
	idx = int(time_from_start // step_sec)
	if idx < 0 or idx >= len(_DEMO_WARNING_SEQUENCE):
		return None

	in_step = time_from_start - idx * step_sec
	if 0.0 <= in_step < _WARNING_DURATION_SEC:
		return _DEMO_WARNING_SEQUENCE[idx]
	return None


def update_state(
	state: dict[str, Any],
	tick: int,
	hz: int,
	gps_lat_offset: float = 0.0,
	gps_lon_offset: float = 0.0,
	timeline_offset_sec: float = 0.0,
) -> dict[str, Any]:
	dt = 1.0 / max(1, hz)
	total_cycle_sec = _ACCEL_SEC + _CRUISE_SEC + _BRAKE_SEC + _STOP_SEC
	cycle_ticks = max(1, int(total_cycle_sec * hz))
	phase_tick = (tick - 1) % cycle_ticks
	elapsed_sec = (phase_tick / max(1, hz) + timeline_offset_sec) % total_cycle_sec

	speed_kph, traction_mode = _speed_profile_kph(elapsed_sec)
	prev_speed_kph = float(state.get("speed_kph", 0.0))
	accel = (speed_kph - prev_speed_kph) / dt / 3.6
	progress = _distance_progress(elapsed_sec)

	lat, lon, seg_idx = _interpolate_route(progress)
	lat += gps_lat_offset
	lon += gps_lon_offset

	in_bad_track_segment = _is_warning_segment(progress)
	active_warning_rule = _active_demo_warning(elapsed_sec)
	allowed_speed = 80.0

	state["speed_kph"] = max(0.0, speed_kph)
	state["target_speed_kph"] = _CRUISE_SPEED_KPH if elapsed_sec < (_ACCEL_SEC + _CRUISE_SEC) else 0.0
	state["allowed_speed_kph"] = allowed_speed
	state["acceleration"] = accel
	state["traction_mode"] = traction_mode

	state["tractive_effort_kn"] = max(0.0, 220.0 * (state["target_speed_kph"] - state["speed_kph"]) / max(1.0, _CRUISE_SPEED_KPH))
	state["traction_power_kw"] = max(0.0, state["tractive_effort_kn"] * state["speed_kph"] / 3.6)
	state["regen_power_kw"] = max(0.0, -accel * 100.0) if traction_mode in {"braking", "regen"} else 0.0
	state["traction_current_a"] = state["traction_power_kw"] * 1000.0 / max(20_000.0, state["catenary_voltage_kv"] * 1000.0)

	state["brake_pipe_pressure_bar"] = 4.2 if traction_mode == "braking" else 5.0
	state["brake_cylinder_pressure_bar"] = 2.0 if traction_mode == "braking" else 0.2

	temp_load = state["traction_power_kw"] / 35_000.0
	state["transformer_temp_c"] = min(110.0, 42.0 + temp_load * 35.0)
	state["converter_temp_c"] = min(105.0, 39.0 + temp_load * 32.0)
	state["traction_motor_temp_c"] = min(120.0, 45.0 + temp_load * 48.0)
	state["axle_bearing_temp_c"] = min(95.0, 36.0 + state["speed_kph"] / 10.0)

	state["pneumatic_pressure_bar"] = 7.1 if traction_mode == "braking" else 7.7
	state["compressor_state"] = "on" if state["pneumatic_pressure_bar"] < 7.2 else "off"
	state["compressor_cycles_per_hour"] = 10.0 if state["compressor_state"] == "on" else 6.0

	state["vibration_motor"] = 0.6 + state["speed_kph"] / 160.0
	state["vibration_gearbox"] = 0.5 + state["speed_kph"] / 190.0

	state["gps_lat"] = lat
	state["gps_lon"] = lon
	state["route_segment"] = f"ALA-NUR:{seg_idx:03d}"
	state["gradient_permille"] = 4.0 if in_bad_track_segment else 0.0
	state["active_fault_codes"] = []
	state["signal_quality"] = 0.96
	state["data_quality"] = 0.98

	if active_warning_rule == "upcoming_bad_track":
		state["active_fault_codes"] = ["UPCOMING_BAD_TRACK"]
	elif active_warning_rule == "high_vibration":
		state["vibration_gearbox"] = max(float(state["vibration_gearbox"]), 3.2)
		state["active_fault_codes"] = ["HIGH_VIBRATION"]
	elif active_warning_rule == "overspeed":
		state["allowed_speed_kph"] = max(20.0, state["speed_kph"] - 8.0)
		state["active_fault_codes"] = ["OVERSPEED"]
	elif active_warning_rule == "high_temperature":
		state["traction_motor_temp_c"] = max(float(state["traction_motor_temp_c"]), 108.0)
		state["active_fault_codes"] = ["HIGH_TEMPERATURE"]
	elif active_warning_rule == "low_signal_quality":
		state["signal_quality"] = 0.72
		state["data_quality"] = 0.78
		state["active_fault_codes"] = ["LOW_SIGNAL_QUALITY"]
	elif active_warning_rule == "voltage_sag":
		state["catenary_voltage_kv"] = 16.5
		state["active_fault_codes"] = ["VOLTAGE_SAG"]

	return state
