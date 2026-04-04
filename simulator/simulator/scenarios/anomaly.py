from __future__ import annotations

from typing import Any


def apply_fault(state: dict[str, Any], scenario: str) -> dict[str, Any]:
	faults: list[str] = []

	if scenario == "overspeed":
		state["allowed_speed_kph"] = 70.0
		state["speed_kph"] = max(state["speed_kph"], 95.0)
		state["target_speed_kph"] = 98.0
		faults.append("OVERSPEED")
	elif scenario == "brake_pressure_drop":
		state["brake_pipe_pressure_bar"] = 2.6
		state["brake_cylinder_pressure_bar"] = 0.1
		state["pneumatic_pressure_bar"] = 4.8
		faults.append("BRAKE_PRESSURE_DROP")
	elif scenario == "motor_overheat":
		state["traction_motor_temp_c"] = 165.0
		state["converter_temp_c"] = 132.0
		state["transformer_temp_c"] = 138.0
		faults.append("MOTOR_OVERHEAT")
	elif scenario == "catenary_voltage_sag":
		state["catenary_voltage_kv"] = 15.5
		state["traction_current_a"] = max(0.0, float(state["traction_current_a"]) * 1.4)
		faults.append("CATENARY_VOLTAGE_SAG")
	elif scenario == "gearbox_vibration_high":
		state["vibration_gearbox"] = 6.5
		state["vibration_motor"] = 4.2
		faults.append("GEARBOX_VIBRATION_HIGH")

	state["active_fault_codes"] = faults
	state["signal_quality"] = 0.88 if faults else 0.96
	state["data_quality"] = 0.9 if faults else 0.98
	return state
