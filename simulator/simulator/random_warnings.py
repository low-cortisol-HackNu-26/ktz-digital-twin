from __future__ import annotations

import os
import random
from dataclasses import dataclass
from typing import Any


_DEFAULT_WARNING_TYPES = [
	"overspeed",
	"high_temperature",
	"high_brakes_temperature",
	"low_signal_quality",
	"voltage_sag",
	"high_vibration",
	"bad_track_upcoming",
	"low_pneumatic_pressure",
]


def _to_bool(raw: str | None, default: bool) -> bool:
	if raw is None:
		return default
	return raw.strip().lower() in {"1", "true", "yes", "on"}


def _to_float(raw: str | None, default: float) -> float:
	if raw is None:
		return default
	try:
		return float(raw)
	except ValueError:
		return default


def _to_int(raw: str | None, default: int) -> int:
	if raw is None:
		return default
	try:
		return int(raw)
	except ValueError:
		return default


@dataclass(slots=True)
class RandomWarningsConfig:
	random_warnings_enabled: bool = True
	warning_duration_seconds: float = 10.0
	warning_cooldown_seconds: float = 2.0
	warning_probability_per_tick: float = 0.06
	enabled_warning_types: list[str] | None = None
	max_active_warnings_per_locomotive: int = 3

	@classmethod
	def from_env(cls) -> "RandomWarningsConfig":
		enabled_raw = os.getenv("ENABLED_WARNING_TYPES")
		enabled = None
		if enabled_raw:
			enabled = [item.strip().lower() for item in enabled_raw.split(",") if item.strip()]

		return cls(
			random_warnings_enabled=_to_bool(os.getenv("RANDOM_WARNINGS_ENABLED"), True),
			warning_duration_seconds=max(1.0, _to_float(os.getenv("WARNING_DURATION_SECONDS"), 6.0)),
			warning_cooldown_seconds=max(0.0, _to_float(os.getenv("WARNING_COOLDOWN_SECONDS"), 4.0)),
			warning_probability_per_tick=min(
				1.0,
				max(0.0, _to_float(os.getenv("WARNING_PROBABILITY_PER_TICK"), 0.015)),
			),
			enabled_warning_types=enabled,
			max_active_warnings_per_locomotive=max(
				1,
				_to_int(os.getenv("MAX_ACTIVE_WARNINGS_PER_LOCOMOTIVE"), 2),
			),
		)

	def is_enabled(self, warning_type: str) -> bool:
		if not self.enabled_warning_types:
			return warning_type in _DEFAULT_WARNING_TYPES
		return warning_type in self.enabled_warning_types


@dataclass(slots=True)
class _WarningLifecycle:
	name: str
	active_ticks_left: int
	recovery_ticks_left: int


class RandomWarningsEngine:
	def __init__(self, locomotive_id: str, hz: int, config: RandomWarningsConfig | None = None) -> None:
		self._loco_id = locomotive_id
		self._hz = max(1, hz)
		self._config = config or RandomWarningsConfig.from_env()
		seed = sum(ord(ch) for ch in locomotive_id) + self._hz * 1009
		self._rng = random.Random(seed)
		self._active: list[_WarningLifecycle] = []
		self._cooldown_ticks_left: int = 0

	def apply(self, state: dict[str, Any], *, cruising: bool, base_route_segment: str) -> dict[str, Any]:
		if not self._config.random_warnings_enabled:
			return state

		self._tick_lifecycles()
		self._maybe_start_warning(state, cruising=cruising)
		self._apply_effects(state, base_route_segment=base_route_segment)
		return state

	def _tick_lifecycles(self) -> None:
		if self._cooldown_ticks_left > 0:
			self._cooldown_ticks_left -= 1

		next_active: list[_WarningLifecycle] = []
		for warning in self._active:
			if warning.active_ticks_left > 0:
				warning.active_ticks_left -= 1
			elif warning.recovery_ticks_left > 0:
				warning.recovery_ticks_left -= 1

			if warning.active_ticks_left > 0 or warning.recovery_ticks_left > 0:
				next_active.append(warning)

		self._active = next_active

	def _maybe_start_warning(self, state: dict[str, Any], *, cruising: bool) -> None:
		if not cruising:
			return

		if self._cooldown_ticks_left > 0:
			return

		if len(self._active) >= self._config.max_active_warnings_per_locomotive:
			return

		if self._rng.random() >= self._config.warning_probability_per_tick:
			return

		active_names = {item.name for item in self._active}
		candidates = [
			name
			for name in _DEFAULT_WARNING_TYPES
			if self._config.is_enabled(name) and name not in active_names
		]
		if not candidates:
			return

		chosen = self._rng.choice(candidates)
		duration_ticks = max(1, int(round(self._config.warning_duration_seconds * self._hz)))
		recovery_ticks = max(1, int(round(2.0 * self._hz)))
		self._active.append(
			_WarningLifecycle(
				name=chosen,
				active_ticks_left=duration_ticks,
				recovery_ticks_left=recovery_ticks,
			)
		)
		self._cooldown_ticks_left = int(round(self._config.warning_cooldown_seconds * self._hz))

	def _apply_effects(self, state: dict[str, Any], *, base_route_segment: str) -> None:
		faults: set[str] = set(str(code).lower() for code in state.get("active_fault_codes", []))
		route_segment = base_route_segment
		traction_type = str(state.get("traction_type") or "electric").lower()

		for warning in self._active:
			progress = self._effect_progress(warning)
			if progress <= 0.0:
				continue

			if warning.name == "overspeed":
				allowed = float(state.get("allowed_speed_kph", 100.0))
				speed = float(state.get("speed_kph", 0.0))
				state["allowed_speed_kph"] = max(20.0, min(allowed, speed - (5.5 * progress)))
				state["speed_kph"] = max(speed, speed + (3.0 * progress))

			elif warning.name == "high_temperature":
				state["traction_motor_temp_c"] = float(state.get("traction_motor_temp_c", 50.0)) + 55.0 * progress
				state["converter_temp_c"] = float(state.get("converter_temp_c", 45.0)) + 32.0 * progress
				if traction_type == "electric":
					state["traction_current_a"] = float(state.get("traction_current_a", 200.0)) + 140.0 * progress

			elif warning.name == "low_signal_quality":
				state["signal_quality"] = max(0.5, float(state.get("signal_quality", 0.96)) - 0.24 * progress)
				state["data_quality"] = max(0.6, float(state.get("data_quality", 0.98)) - 0.15 * progress)

			elif warning.name == "voltage_sag":
				if traction_type == "electric":
					state["catenary_voltage_kv"] = max(15.2, float(state.get("catenary_voltage_kv", 25.0)) - 9.0 * progress)
					state["traction_power_kw"] = max(0.0, float(state.get("traction_power_kw", 0.0)) * (1.0 - 0.28 * progress))
					state["traction_current_a"] = float(state.get("traction_current_a", 150.0)) + 120.0 * progress

			elif warning.name == "high_vibration":
				state["vibration_gearbox"] = float(state.get("vibration_gearbox", 0.8)) + 2.4 * progress

			elif warning.name == "high_brakes_temperature":
				# Cap at 210 °C — backend schema rejects values > 220 °C, and
				# _apply_live_metric_dynamics already clamps to 165 °C so an
				# uncapped +160 would produce ~325 °C and cause 422 failures.
				state["brakes_temperature_c"] = min(
					210.0,
					float(state.get("brakes_temperature_c", 40.0)) + 160.0 * progress,
				)

			elif warning.name == "low_pneumatic_pressure":
				state["pneumatic_pressure_bar"] = max(3.5, float(state.get("pneumatic_pressure_bar", 7.5)) - 3.5 * progress)
				state["compressor_state"] = "on"
				state["compressor_cycles_per_hour"] = min(60.0, float(state.get("compressor_cycles_per_hour", 9.0)) + 20.0 * progress)

			elif warning.name == "bad_track_upcoming":
				faults.add("upcoming_bad_track")
				state["allowed_speed_kph"] = max(25.0, float(state.get("allowed_speed_kph", 95.0)) - 20.0 * progress)
				state["vibration_gearbox"] = float(state.get("vibration_gearbox", 0.8)) + 0.7 * progress
				state["brakes_temperature_c"] = float(state.get("brakes_temperature_c", 40.0)) + 8.0 * progress
				route_segment = f"{base_route_segment}:bad_track"

		if "signal_quality" in state:
			state["signal_quality"] = min(1.0, max(0.0, float(state["signal_quality"])))
		if "data_quality" in state:
			state["data_quality"] = min(1.0, max(0.0, float(state["data_quality"])))

		state["active_fault_codes"] = sorted(faults)
		state["route_segment"] = route_segment
		state["engine_temperature_c"] = float(state.get("traction_motor_temp_c", 0.0))
		state["pressure_bar"] = float(state.get("brake_pipe_pressure_bar", 0.0))
		voltage = state.get("catenary_voltage_kv")
		current = state.get("traction_current_a")
		state["voltage_kv"] = float(voltage) if voltage is not None else None
		state["current_a"] = float(current) if current is not None else None

	def _effect_progress(self, warning: _WarningLifecycle) -> float:
		total_active = max(1, int(round(self._config.warning_duration_seconds * self._hz)))
		total_recovery = max(1, int(round(2.0 * self._hz)))
		if warning.active_ticks_left > 0:
			elapsed = total_active - warning.active_ticks_left
			ramp_in = min(1.0, elapsed / max(1, int(0.35 * self._hz)))
			return max(0.0, min(1.0, ramp_in))

		if warning.recovery_ticks_left > 0:
			return warning.recovery_ticks_left / total_recovery

		return 0.0
