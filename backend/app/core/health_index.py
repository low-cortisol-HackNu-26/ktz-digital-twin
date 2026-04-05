from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
	"""100 when value ≤ warning_at, 0 when value ≥ critical_at, linear in between."""
	if value is None:
		return 100.0
	if value <= warning_at:
		return 100.0
	if value >= critical_at:
		return 0.0
	span = max(1e-6, critical_at - warning_at)
	return _clamp((critical_at - value) / span * 100.0, 0.0, 100.0)


def _score_high_is_good(value: float | None, *, warning_below: float, critical_below: float) -> float:
	"""100 when value ≥ warning_below, 0 when value ≤ critical_below, linear in between."""
	if value is None:
		return 100.0
	if value >= warning_below:
		return 100.0
	if value <= critical_below:
		return 0.0
	span = max(1e-6, warning_below - critical_below)
	return _clamp((value - critical_below) / span * 100.0, 0.0, 100.0)


def _weighted_mean(items: list[tuple[float, float]]) -> float:
	"""Weighted average of (score, weight) pairs, clamped to [0, 100]."""
	if not items:
		return 100.0
	total_weight = sum(w for _, w in items)
	if total_weight <= 0.0:
		return 100.0
	return _clamp(sum(s * w for s, w in items) / total_weight, 0.0, 100.0)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class HealthIndexResult:
	overall_health_index: float
	electricity_health: float   # thermal + energy/fuel
	brake_health: float         # brakes temp + effectiveness + vibration
	pressure_health: float      # brake pipe + pneumatic
	voltage_health: float       # catenary voltage + signal quality
	current_health: float       # traction current
	top_factors: list[str]
	timestamp: datetime | None


# ---------------------------------------------------------------------------
# Main computation
# ---------------------------------------------------------------------------

def compute_health_index(event: Any) -> HealthIndexResult:
	"""Compute a 0–100 health index from five physical subsystem domains.

	Domain weights reflect safety criticality:
	  electricity  0.25  — drivetrain heat + energy / fuel
	  brake        0.25  — brake heat + effectiveness + vibration
	  pressure     0.22  — pneumatic integrity (pipe + reservoir)
	  voltage      0.17  — supply quality + signal/data link
	  current      0.11  — traction current load
	"""

	traction_type = str(_read(event, "traction_type") or "electric").lower()

	# ── 1. ELECTRICITY HEALTH (weight 0.25) ─────────────────────────────────
	# Drivetrain temperatures (all motors, transformers, converters).
	# High temperatures → risk of thermal runaway. Thresholds match frontend DRIVE_TEMP_*.
	transformer_temp  = _to_float(_read(event, "transformer_temp_c"))
	converter_temp    = _to_float(_read(event, "converter_temp_c"))
	motor_temp        = _to_float(_read(event, "traction_motor_temp_c"))
	engine_temp       = _to_float(_read(event, "engine_temperature_c"))

	candidates = [v for v in [transformer_temp, converter_temp, motor_temp, engine_temp] if v is not None]
	max_drive_temp = max(candidates) if candidates else None

	drive_temp_score = _score_low_is_good(
		max_drive_temp,
		warning_at=90.0,    # frontend DRIVE_TEMP_WARN_C = 95; we score earlier
		critical_at=115.0,  # frontend DRIVE_TEMP_CRIT_C = 110; slight buffer
	)

	# Energy / fuel — how hard is the locomotive working?
	# Electric: energy_consumption_kwh (absolute kWh in session — high is worse).
	# Diesel:   fuel_level_percent     (remaining — low is worse).
	if traction_type == "diesel":
		fuel_pct = _to_float(_read(event, "fuel_level_percent"))
		resource_score = _score_high_is_good(
			fuel_pct,
			warning_below=70.0,   # frontend FUEL_PCT_WARN_BELOW
			critical_below=40.0,  # frontend FUEL_PCT_CRIT_BELOW
		)
	else:
		energy_kwh = _to_float(_read(event, "energy_consumption_kwh"))
		resource_score = _score_low_is_good(
			energy_kwh,
			warning_at=7.0,   # frontend ENERGY_ABS_WARN
			critical_at=9.0,  # frontend ENERGY_ABS_CRIT
		)

	electricity_health = _weighted_mean([
		(drive_temp_score, 0.65),
		(resource_score,   0.35),
	])

	# ── 2. BRAKE HEALTH (weight 0.25) ────────────────────────────────────────
	# Brake temperature — excess heat degrades lining and risks fade.
	# Thresholds align with frontend BRAKES_TEMP_*.
	brake_temp = _to_float(_read(event, "brakes_temperature_c"))
	brake_temp_score = _score_low_is_good(
		brake_temp,
		warning_at=130.0,   # frontend BRAKES_TEMP_WARN_C = 140; stricter
		critical_at=168.0,  # frontend BRAKES_TEMP_CRIT_C = 180; stricter
	)

	# Brake cylinder effectiveness — only meaningful while braking.
	traction_mode = str(_read(event, "traction_mode") or "coast").lower()
	brake_cylinder = _to_float(_read(event, "brake_cylinder_pressure_bar"))
	if traction_mode == "braking":
		if brake_cylinder is None:
			effectiveness_score = 100.0
		elif brake_cylinder >= 1.8:
			effectiveness_score = 100.0
		elif brake_cylinder <= 0.3:
			effectiveness_score = 0.0
		else:
			effectiveness_score = _clamp((brake_cylinder - 0.3) / 1.5 * 100.0, 0.0, 100.0)
	else:
		effectiveness_score = 100.0

	# Vibration — gearbox and motor vibration indicate mechanical wear.
	vib_gearbox = _to_float(_read(event, "vibration_gearbox"))
	vib_motor   = _to_float(_read(event, "vibration_motor"))
	vib_vals    = [v for v in [vib_gearbox, vib_motor] if v is not None]
	max_vib     = max(vib_vals) if vib_vals else None
	vibration_score = _score_low_is_good(
		max_vib,
		warning_at=1.5,   # g — elevated but manageable
		critical_at=3.5,  # g — risk of structural damage
	)

	brake_health = _weighted_mean([
		(brake_temp_score,    0.55),
		(effectiveness_score, 0.25),
		(vibration_score,     0.20),
	])

	# ── 3. PRESSURE HEALTH (weight 0.22) ─────────────────────────────────────
	# Brake pipe pressure — below 4.2 bar the automatic brake begins to apply.
	pipe_raw    = _to_float(_read(event, "brake_pipe_pressure_bar"))
	pipe_alias  = _to_float(_read(event, "pressure_bar"))
	pipe_pressure = pipe_raw if pipe_raw is not None else pipe_alias
	pipe_score = _score_high_is_good(
		pipe_pressure,
		warning_below=4.2,   # train pipe nominal ~5 bar; warn earlier than warning alert
		critical_below=3.5,  # emergency brake threshold
	)

	# Pneumatic reservoir — must stay charged for repeated brake applications.
	# Thresholds align with frontend PNEUMATIC_*.
	pneumatic = _to_float(_read(event, "pneumatic_pressure_bar"))
	pneumatic_score = _score_high_is_good(
		pneumatic,
		warning_below=6.5,   # frontend PNEUMATIC_WARN_BAR = 6; stricter
		critical_below=5.5,  # frontend PNEUMATIC_CRIT_BAR = 5; stricter
	)

	pressure_health = _weighted_mean([
		(pipe_score,      0.55),
		(pneumatic_score, 0.45),
	])

	# ── 4. VOLTAGE HEALTH (weight 0.17) ──────────────────────────────────────
	# Catenary voltage — sags increase current draw and cause control instability.
	# Thresholds match frontend VOLTAGE_*.
	voltage_raw   = _to_float(_read(event, "catenary_voltage_kv"))
	voltage_alias = _to_float(_read(event, "voltage_kv"))
	voltage = voltage_raw if voltage_raw is not None else voltage_alias
	voltage_score = _score_high_is_good(
		voltage,
		warning_below=21.0,  # frontend VOLTAGE_WARN_KV = 20; stricter
		critical_below=18.0, # frontend VOLTAGE_CRIT_KV = 17; stricter
	)

	# Signal / data quality — degraded telemetry masks real faults.
	sig_quality  = _to_float(_read(event, "signal_quality"))
	data_quality = _to_float(_read(event, "data_quality"))
	min_quality  = min(
		sig_quality  if sig_quality  is not None else 1.0,
		data_quality if data_quality is not None else 1.0,
	)
	signal_score = _score_high_is_good(
		min_quality,
		warning_below=0.85,  # below 85 % link quality, readings become unreliable
		critical_below=0.70, # below 70 % serious data integrity risk
	)

	# For diesel locos catenary voltage is not applicable — use signal only.
	if traction_type == "diesel":
		voltage_health = signal_score
	else:
		voltage_health = _weighted_mean([
			(voltage_score, 0.70),
			(signal_score,  0.30),
		])

	# ── 5. CURRENT HEALTH (weight 0.11) ──────────────────────────────────────
	# Sustained high current overheats windings and accelerates insulation wear.
	current_raw   = _to_float(_read(event, "traction_current_a"))
	current_alias = _to_float(_read(event, "current_a"))
	current = current_raw if current_raw is not None else current_alias
	current_health = _score_low_is_good(
		current,
		warning_at=850.0,    # above this, sustained draw starts degrading insulation
		critical_at=1200.0,  # above this, thermal protection trips imminent
	)

	# ── OVERALL ──────────────────────────────────────────────────────────────
	domain_scores: dict[str, float] = {
		"electricity": electricity_health,
		"brake":       brake_health,
		"pressure":    pressure_health,
		"voltage":     voltage_health,
		"current":     current_health,
	}
	domain_weights: dict[str, float] = {
		"electricity": 0.25,
		"brake":       0.25,
		"pressure":    0.22,
		"voltage":     0.17,
		"current":     0.11,
	}

	overall_health_index = _weighted_mean(
		[(domain_scores[name], domain_weights[name]) for name in domain_scores]
	)

	# Top degraded factors for display (worst first, only below 95).
	factors_sorted = sorted(domain_scores.items(), key=lambda kv: kv[1])
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
