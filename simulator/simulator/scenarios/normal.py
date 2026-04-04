from __future__ import annotations

from typing import Any

# KZ8A electric locomotive physics constants
_MAX_SPEED_KPH = 120.0
_TRACTION_ACCEL = 0.6		# m/s²  — motoring
_SERVICE_BRAKE_DECEL = 0.8	# m/s²  — normal service brake


def update_physics(state: dict[str, Any], target_speed_kph: float, hz: int) -> dict[str, Any]:
	"""Advance one tick towards target_speed_kph using realistic physics."""
	dt = 1.0 / max(1, hz)
	prev_ms = float(state["speed_kph"]) / 3.6
	target_ms = max(0.0, min(_MAX_SPEED_KPH, target_speed_kph)) / 3.6

	delta_ms = target_ms - prev_ms
	if delta_ms > 0.05:
		new_ms = prev_ms + min(delta_ms, _TRACTION_ACCEL * dt)
		state["traction_mode"] = "traction"
	elif delta_ms < -0.05:
		new_ms = prev_ms - min(-delta_ms, _SERVICE_BRAKE_DECEL * dt)
		state["traction_mode"] = "braking"
	else:
		new_ms = prev_ms
		state["traction_mode"] = "coast"

	new_ms = max(0.0, new_ms)
	new_kph = new_ms * 3.6
	accel = (new_ms - prev_ms) / dt

	state["speed_kph"] = new_kph
	state["target_speed_kph"] = target_speed_kph
	state["acceleration"] = accel

	state["tractive_effort_kn"] = max(0.0, 260.0 * max(0.0, accel) / _TRACTION_ACCEL)
	state["traction_power_kw"] = max(0.0, state["tractive_effort_kn"] * new_kph / 3.6)
	state["regen_power_kw"] = max(0.0, -accel * 120.0) if accel < 0 else 0.0
	state["traction_current_a"] = (
		state["traction_power_kw"] * 1000.0
		/ max(20_000.0, float(state["catenary_voltage_kv"]) * 1000.0)
	)

	if state["traction_mode"] == "braking":
		state["brake_pipe_pressure_bar"] = 4.1
		state["brake_cylinder_pressure_bar"] = 2.0
	else:
		state["brake_pipe_pressure_bar"] = 5.0
		state["brake_cylinder_pressure_bar"] = 0.2

	load = state["traction_power_kw"] / 30_000.0
	state["transformer_temp_c"] = min(110.0, 42.0 + load * 40.0)
	state["converter_temp_c"] = min(105.0, 39.0 + load * 35.0)
	state["traction_motor_temp_c"] = min(120.0, 45.0 + load * 55.0)
	state["axle_bearing_temp_c"] = min(95.0, 36.0 + new_kph / 8.0)

	state["pneumatic_pressure_bar"] = 7.1 if traction_mode == "braking" else 7.7
	state["compressor_state"] = "on" if state["pneumatic_pressure_bar"] < 7.2 else "off"
	state["compressor_cycles_per_hour"] = 10.0 if state["compressor_state"] == "on" else 6.0

	state["vibration_motor"] = 0.6 + new_kph / 150.0
	state["vibration_gearbox"] = 0.5 + new_kph / 180.0

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


def update_state(state: dict[str, Any], tick: int, hz: int) -> dict[str, Any]:
	"""Legacy shim used by anomaly scenarios — cruises at 80 kph."""
	return update_physics(state, target_speed_kph=80.0, hz=hz)
