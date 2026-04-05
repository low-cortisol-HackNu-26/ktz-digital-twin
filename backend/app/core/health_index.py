from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


def _clamp(value: float, lo: float, hi: float) -> float:
	return max(lo, min(hi, value))


def _read(source: Any, key: str) -> Any:
	if hasattr(source, key):
		return getattr(source, key)
	if isinstance(source, dict):
		return source.get(key)
	return None


def _to_float(value: Any) -> float | None:
	if value is None:
		return None
	try:
		return float(value)
	except (TypeError, ValueError):
		return None


def _score_low_is_good(value: float | None, *, warning_at: float, critical_at: float) -> float:
	if value is None:
		return 100.0
	if value <= warning_at:
		return 100.0
	if value >= critical_at:
		return 0.0
	span = max(1e-6, critical_at - warning_at)
	return _clamp((critical_at - value) / span * 100.0, 0.0, 100.0)


def _score_high_is_good(value: float | None, *, warning_below: float, critical_below: float) -> float:
	if value is None:
		return 100.0
	if value >= warning_below:
		return 100.0
	if value <= critical_below:
		return 0.0
	span = max(1e-6, warning_below - critical_below)
	return _clamp((value - critical_below) / span * 100.0, 0.0, 100.0)


def _weighted_mean(items: list[tuple[float, float]]) -> float:
	if not items:
		return 100.0
	total_weight = sum(weight for _, weight in items)
	if total_weight <= 0.0:
		return 100.0
	return _clamp(sum(score * weight for score, weight in items) / total_weight, 0.0, 100.0)


@dataclass(slots=True)
class HealthIndexResult:
	overall_health_index: float
	electricity_health: float
	brake_health: float
	pressure_health: float
	voltage_health: float
	current_health: float
	top_factors: list[str]
	timestamp: datetime | None


def compute_health_index(event: Any) -> HealthIndexResult:
	"""Compute backend health index from core domains only.

	Direct speed scoring is intentionally excluded. Speed may affect health only
	indirectly through other telemetry metrics (temperature, pressure, current, etc.).
	"""

	transformer_temp = _to_float(_read(event, "transformer_temp_c"))
	converter_temp = _to_float(_read(event, "converter_temp_c"))
	traction_motor_temp = _to_float(_read(event, "traction_motor_temp_c"))
	engine_temp = _to_float(_read(event, "engine_temperature_c"))

	max_electric_temp = max(
		[value for value in [transformer_temp, converter_temp, traction_motor_temp, engine_temp] if value is not None],
		default=None,
	)
	traction_power_kw = _to_float(_read(event, "traction_power_kw"))
	electricity_health = _weighted_mean(
		[
			(_score_low_is_good(max_electric_temp, warning_at=95.0, critical_at=125.0), 0.65),
			(_score_low_is_good(traction_power_kw, warning_at=9000.0, critical_at=14500.0), 0.35),
		]
	)

	brake_temp = _to_float(_read(event, "brakes_temperature_c"))
	brake_cylinder = _to_float(_read(event, "brake_cylinder_pressure_bar"))
	traction_mode = str(_read(event, "traction_mode") or "coast").lower()
	if traction_mode == "braking":
		if brake_cylinder is None:
			brake_effectiveness = 100.0
		elif brake_cylinder >= 1.6:
			brake_effectiveness = 100.0
		elif brake_cylinder <= 0.4:
			brake_effectiveness = 0.0
		else:
			brake_effectiveness = _clamp((brake_cylinder - 0.4) / 1.2 * 100.0, 0.0, 100.0)
	else:
		brake_effectiveness = 100.0
	brake_health = _weighted_mean(
		[
			(_score_low_is_good(brake_temp, warning_at=105.0, critical_at=145.0), 0.7),
			(brake_effectiveness, 0.3),
		]
	)

	pipe_pressure = _to_float(_read(event, "brake_pipe_pressure_bar"))
	pressure_alias = _to_float(_read(event, "pressure_bar"))
	pneumatic_pressure = _to_float(_read(event, "pneumatic_pressure_bar"))
	pressure_health = _weighted_mean(
		[
			(_score_high_is_good(pipe_pressure if pipe_pressure is not None else pressure_alias, warning_below=4.0, critical_below=3.0), 0.6),
			(_score_high_is_good(pneumatic_pressure, warning_below=6.6, critical_below=5.8), 0.4),
		]
	)

	voltage = _to_float(_read(event, "catenary_voltage_kv"))
	voltage_alias = _to_float(_read(event, "voltage_kv"))
	voltage_health = _score_high_is_good(
		voltage if voltage is not None else voltage_alias,
		warning_below=20.0,
		critical_below=17.0,
	)

	current = _to_float(_read(event, "traction_current_a"))
	current_alias = _to_float(_read(event, "current_a"))
	current_health = _score_low_is_good(
		current if current is not None else current_alias,
		warning_at=950.0,
		critical_at=1250.0,
	)

	domain_scores = {
		"electricity": electricity_health,
		"brake": brake_health,
		"pressure": pressure_health,
		"voltage": voltage_health,
		"current": current_health,
	}
	domain_weights = {
		"electricity": 0.26,
		"brake": 0.20,
		"pressure": 0.20,
		"voltage": 0.17,
		"current": 0.17,
	}

	overall_health_index = _weighted_mean(
		[(domain_scores[name], domain_weights[name]) for name in ["electricity", "brake", "pressure", "voltage", "current"]]
	)

	factors_sorted = sorted(
		domain_scores.items(),
		key=lambda item: item[1],
	)
	top_factors = [
		f"{name}_health={score:.1f}"
		for name, score in factors_sorted
		if score < 95.0
	][:5]
	if not top_factors:
		top_factors = ["All core subsystem metrics are within expected range"]

	timestamp = _read(event, "timestamp")
	if timestamp is not None and not isinstance(timestamp, datetime):
		timestamp = None

	return HealthIndexResult(
		overall_health_index=round(overall_health_index, 2),
		electricity_health=round(electricity_health, 2),
		brake_health=round(brake_health, 2),
		pressure_health=round(pressure_health, 2),
		voltage_health=round(voltage_health, 2),
		current_health=round(current_health, 2),
		top_factors=top_factors,
		timestamp=timestamp,
	)
