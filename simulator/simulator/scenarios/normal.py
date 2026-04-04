from __future__ import annotations

from typing import Any


def update_state(state: dict[str, Any], tick: int, hz: int) -> dict[str, Any]:
	cycle = max(1, 240 * hz)
	phase = tick % cycle

	if phase < 40 * hz:
		speed_target = 45.0
		state["traction_mode"] = "traction"
		state["allowed_speed_kph"] = 80.0
	elif phase < 180 * hz:
		speed_target = 78.0
		state["traction_mode"] = "coast"
		state["allowed_speed_kph"] = 80.0
	elif phase < 210 * hz:
		speed_target = 28.0
		state["traction_mode"] = "braking"
	else:
		speed_target = 0.0
		state["traction_mode"] = "regen"

	prev = float(state["speed_kph"])
	alpha = 0.06
	speed = prev + (speed_target - prev) * alpha
	dt = 1.0 / max(1, hz)
	accel = (speed - prev) / dt / 3.6

	state["speed_kph"] = max(0.0, speed)
	state["target_speed_kph"] = speed_target
	state["acceleration"] = accel
	state["tractive_effort_kn"] = max(0.0, 260.0 * (speed_target - speed) / 80.0)
	state["traction_power_kw"] = max(0.0, state["tractive_effort_kn"] * state["speed_kph"] / 3.6)
	state["regen_power_kw"] = max(0.0, -accel * 120.0) if state["traction_mode"] in {"braking", "regen"} else 0.0

	state["traction_current_a"] = state["traction_power_kw"] * 1000.0 / max(20_000.0, state["catenary_voltage_kv"] * 1000.0)

	state["brake_pipe_pressure_bar"] = 5.0 if state["traction_mode"] != "braking" else 4.1
	state["brake_cylinder_pressure_bar"] = 0.2 if state["traction_mode"] != "braking" else 2.0

	temp_rise = state["traction_power_kw"] / 30_000.0
	state["transformer_temp_c"] = min(110.0, 42.0 + temp_rise * 40.0)
	state["converter_temp_c"] = min(105.0, 39.0 + temp_rise * 35.0)
	state["traction_motor_temp_c"] = min(120.0, 45.0 + temp_rise * 55.0)
	state["axle_bearing_temp_c"] = min(95.0, 36.0 + state["speed_kph"] / 8.0)

	state["pneumatic_pressure_bar"] = 7.7 if state["traction_mode"] != "braking" else 7.1
	state["compressor_state"] = "on" if state["pneumatic_pressure_bar"] < 7.2 else "off"
	state["compressor_cycles_per_hour"] = 10.0 if state["compressor_state"] == "on" else 6.0

	state["vibration_motor"] = 0.6 + state["speed_kph"] / 150.0
	state["vibration_gearbox"] = 0.5 + state["speed_kph"] / 180.0

	state["gradient_permille"] = 6.0 if 100 * hz < phase < 130 * hz else 0.0
	state["active_fault_codes"] = []
	state["signal_quality"] = 0.96
	state["data_quality"] = 0.98
	return state
