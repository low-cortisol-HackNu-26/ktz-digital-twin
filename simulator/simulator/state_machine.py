from __future__ import annotations

import json
import math
from copy import deepcopy
from enum import Enum, auto
from pathlib import Path
from typing import Any

from .packets import DEFAULT_INITIAL_STATE, build_packet
from .random_warnings import RandomWarningsEngine
from .route_context import context_for_segment
from .route_follower import RouteFollower
from .scenarios.anomaly import apply_fault
from .scenarios.normal import _MAX_SPEED_KPH, update_physics

# ---------------------------------------------------------------------------
# Route data
# ---------------------------------------------------------------------------

_ROUTES_FILE = Path(__file__).parent.parent / "data" / "ktz_routes.json"

_FALLBACK_ROUTES: list[dict] = [
	{
		"code": "ALA-NUR", "name": "Almaty — Nur-Sultan", "total_length_km": 1295.0,
		"coordinates": [
			[76.9286, 43.2567], [77.0500, 43.8500], [77.1200, 44.4000],
			[77.0000, 44.8500], [76.1500, 45.5000], [75.3000, 46.2000],
			[74.9950, 46.8474], [74.0000, 47.8000], [73.6000, 48.6000],
			[73.0884, 49.8073], [72.5000, 50.4000], [71.9500, 50.8500],
			[71.4460, 51.1801],
		],
	},
	{
		"code": "ALA-SHY", "name": "Almaty — Shymkent", "total_length_km": 705.0,
		"coordinates": [
			[76.9286, 43.2567], [76.0000, 43.0000], [74.5000, 42.8500],
			[73.0000, 42.7000], [71.9000, 42.6000], [71.3713, 42.3167],
			[70.8000, 42.2000], [69.5900, 42.3170],
		],
	},
	{
		"code": "NUR-AKT", "name": "Nur-Sultan — Aktobe", "total_length_km": 1090.0,
		"coordinates": [
			[71.4460, 51.1801], [70.0000, 51.5000], [68.0000, 52.0000],
			[66.0000, 52.5000], [64.5000, 52.8000], [63.6240, 53.2143],
			[62.0000, 52.5000], [60.0000, 51.5000], [57.1530, 50.3001],
		],
	},
	{
		"code": "NUR-PET", "name": "Nur-Sultan — Petropavl", "total_length_km": 280.0,
		"coordinates": [
			[71.4460, 51.1801], [71.5000, 51.8000], [71.6000, 52.4000],
			[71.7000, 52.9000], [71.9522, 54.8650],
		],
	},
	{
		"code": "SHY-KYZ", "name": "Shymkent — Kyzylorda", "total_length_km": 605.0,
		"coordinates": [
			[69.5900, 42.3170], [68.5000, 43.0000], [67.5000, 43.8000],
			[66.8000, 44.3000], [65.5500, 44.8530],
		],
	},
]

_ROUTES: list[dict] = []
if _ROUTES_FILE.exists():
	try:
		_ROUTES = json.loads(_ROUTES_FILE.read_text())
	except Exception:
		pass
if not _ROUTES:
	_ROUTES = _FALLBACK_ROUTES

_loco_registry: dict[str, int] = {}
_next_index = 0


def _assign_route(locomotive_id: str) -> dict:
	global _next_index
	if locomotive_id not in _loco_registry:
		_loco_registry[locomotive_id] = _next_index % len(_ROUTES)
		_next_index += 1
	return _ROUTES[_loco_registry[locomotive_id]]


def _infer_traction_type(locomotive_id: str) -> str:
	loco = locomotive_id.strip().lower()
	if loco.startswith("dsl") or "diesel" in loco or loco.startswith("fuel"):
		return "diesel"
	return "electric"


# ---------------------------------------------------------------------------
# Journey FSM states
# ---------------------------------------------------------------------------

class _State(Enum):
	RUNNING = auto()		# cruising or braking — physics driven by target speed
	STOPPED = auto()		# dwell at intermediate station
	TERMINUS_WAIT = auto()	# turnaround pause at end of line


# Tuning
_CRUISE_KPH = 100.0		# normal line speed
_APPROACH_KPH = 25.0	# crawl speed in last km before station
_BRAKE_START_KM = 4.0	# start reducing speed this far before station
_APPROACH_START_KM = 1.0	# switch to crawl this far before station
_STOP_THRESHOLD_KM = 0.05	# declare arrival within 50 m
_DWELL_TICKS_BASE = 60		# ~12 s at 5 Hz
_TERMINUS_TICKS = 150		# ~30 s at 5 Hz


class StateMachine:
	def __init__(self, locomotive_id: str, scenario: str, hz: int) -> None:
		self.locomotive_id = locomotive_id
		self.scenario = scenario
		self.hz = max(1, hz)
		self.tick = 0
		self.state: dict[str, Any] = deepcopy(DEFAULT_INITIAL_STATE)
		self._traction_type = _infer_traction_type(locomotive_id)
		self.state["traction_type"] = self._traction_type

		route = _assign_route(locomotive_id)
		route_idx = _loco_registry[locomotive_id]
		start_fraction = (route_idx * 0.3) % 1.0

		self._follower = RouteFollower(route, start_fraction=start_fraction)

		# Journey FSM — start RUNNING (physics will accelerate from rest)
		self._journey: _State = _State.RUNNING
		self._dwell_remaining: int = 0
		self._current_station_name: str = ""
		# Locked-in target station km once we start braking for it
		self._target_station_km: float | None = None
		self._fixed_fault_scenarios = {
			"overspeed", "brake_pressure_drop", "motor_overheat",
			"catenary_voltage_sag", "gearbox_vibration_high",
		}
		self._random_warnings = RandomWarningsEngine(locomotive_id=locomotive_id, hz=self.hz)
		seed = sum(ord(ch) for ch in locomotive_id)
		self._metric_phase = (seed % 360) * (math.pi / 180.0)
		self._fuel_burn_rate_moving = 0.00095 + ((seed % 7) * 0.00003)
		self._fuel_burn_rate_idle = 0.00009 + ((seed % 5) * 0.00001)
		self._engine_temp_bias = ((seed % 9) - 4) * 0.6
		self._brake_temp_bias = ((seed % 11) - 5) * 0.5
		self._pressure_bias = ((seed % 7) - 3) * 0.03
		self._voltage_bias = ((seed % 5) - 2) * 0.12
		self._current_scale = 1.0 + (((seed % 9) - 4) * 0.02)

		# Store route info
		self._route_code = route.get("code", "UNKNOWN")
		self._route_name = route.get("name", "Unknown Route")
		self._last_heading: float | None = None

		# Prime GPS
		self.state["gps_lat"] = self._follower.lat
		self.state["gps_lon"] = self._follower.lng
		self.state["route_segment"] = self._follower.segment_label

	# ------------------------------------------------------------------

	def next_packet(self) -> dict[str, Any]:
		self.tick += 1

		self._apply_route_context()
		target_speed = self._journey_target_speed()
		allowed_speed = float(self.state.get("allowed_speed_kph", target_speed))
		target_speed = min(target_speed, allowed_speed)

		self.state = update_physics(self.state, target_speed, self.hz)
		self._apply_live_metric_dynamics()
		self._apply_environmental_effects()

		if self.scenario in self._fixed_fault_scenarios:
			self.state = apply_fault(self.state, self.scenario)

		# Advance GPS only while moving
		speed_kph = float(self.state["speed_kph"])
		if speed_kph > 0.1:
			distance_km = speed_kph / (self.hz * 3600.0)
			self._follower.advance(distance_km)

		self.state["gps_lat"] = self._follower.lat
		self.state["gps_lon"] = self._follower.lng
		self.state["route_segment"] = self._follower.segment_label
		self._apply_route_context()

		if self.scenario not in self._fixed_fault_scenarios:
			self.state = self._random_warnings.apply(
				self.state,
				cruising=self._journey == _State.RUNNING and float(self.state["speed_kph"]) > 35.0,
				base_route_segment=self._follower.segment_label,
			)

		# Post-fault and post-warning safety clamp: never exceed configured hard cap.
		self.state["speed_kph"] = max(0.0, min(float(self.state.get("speed_kph", 0.0)), float(_MAX_SPEED_KPH)))

		self._synchronize_metric_aliases()

		# Add route and heading info
		self._compute_heading()
		self.state["heading"] = self._last_heading
		self.state["route_code"] = self._route_code
		self.state["route_name"] = self._route_name

		return build_packet(self.locomotive_id, self.state)

	def _compute_heading(self) -> None:
		"""Compute heading (bearing) from current position to next coordinate."""
		coords = self._follower.coords
		if len(coords) < 2:
			self._last_heading = 0.0
			return
		
		seg = self._follower._segment_index()
		if seg < 0 or seg >= len(coords) - 1:
			self._last_heading = 0.0
			return

		from_coord = coords[seg]
		to_coord = coords[seg + 1]
		
		dlon = math.radians(to_coord[0] - from_coord[0])
		lat1 = math.radians(from_coord[1])
		lat2 = math.radians(to_coord[1])
		
		x = math.sin(dlon) * math.cos(lat2)
		y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
		
		heading = (math.degrees(math.atan2(x, y)) + 360) % 360
		self._last_heading = heading

	def _apply_route_context(self) -> None:
		segment_label = self._follower.segment_label
		segment_index = self._segment_index_from_label(segment_label)
		distance_to_station_km = self._follower.distance_to_next_station_km()
		context = context_for_segment(segment_index, distance_to_station_km)
		self.state["route_segment"] = segment_label
		self.state["allowed_speed_kph"] = context.allowed_speed_kph
		self.state["track_condition"] = context.track_condition
		self.state["weather_condition"] = context.weather_condition

	def _apply_environmental_effects(self) -> None:
		track = str(self.state.get("track_condition") or "normal")
		weather = str(self.state.get("weather_condition") or "clear")
		faults = {str(code).lower() for code in self.state.get("active_fault_codes", [])}

		if track == "rough":
			self.state["vibration_gearbox"] = float(self.state["vibration_gearbox"]) + 0.35
		elif track == "bad":
			self.state["vibration_gearbox"] = float(self.state["vibration_gearbox"]) + 0.85
			faults.add("upcoming_bad_track")
		elif track == "maintenance_zone":
			self.state["vibration_gearbox"] = float(self.state["vibration_gearbox"]) + 0.55
			faults.add("upcoming_bad_track")

		if weather == "rain":
			self.state["signal_quality"] = max(0.82, float(self.state.get("signal_quality", 0.96)) - 0.04)
		elif weather == "snow":
			self.state["signal_quality"] = max(0.78, float(self.state.get("signal_quality", 0.96)) - 0.07)
		elif weather == "fog":
			self.state["signal_quality"] = max(0.76, float(self.state.get("signal_quality", 0.96)) - 0.09)
		elif weather == "wind":
			self.state["signal_quality"] = max(0.86, float(self.state.get("signal_quality", 0.96)) - 0.03)

		self.state["active_fault_codes"] = sorted(faults)

	def _apply_live_metric_dynamics(self) -> None:
		dt = 1.0 / self.hz
		speed_kph = float(self.state.get("speed_kph", 0.0))
		accel = float(self.state.get("acceleration", 0.0))
		mode = str(self.state.get("traction_mode") or "coast")
		faults = {str(code).upper() for code in self.state.get("active_fault_codes", [])}
		wave = math.sin(self.tick / (self.hz * 7.0) + self._metric_phase)

		moving = speed_kph > 2.0
		if moving:
			burn = self._fuel_burn_rate_moving * (0.7 + min(1.3, speed_kph / 90.0))
		else:
			burn = self._fuel_burn_rate_idle

		if self._traction_type == "diesel":
			fuel = float(self.state.get("fuel_level_percent", 85.0)) - burn
			self.state["fuel_level_percent"] = max(5.0, min(100.0, fuel))
			self.state["fuel_consumption_lph"] = round(max(2.0, burn * self.hz * 3600.0 * 0.85), 3)
		else:
			self.state["fuel_level_percent"] = None
			self.state["fuel_consumption_lph"] = None

		engine_temp = float(self.state.get("traction_motor_temp_c", 45.0))
		if mode == "traction" and accel > 0.05:
			engine_temp += (0.42 + 0.22 * min(1.0, speed_kph / 100.0)) * dt * self.hz
		elif mode == "braking":
			engine_temp -= 0.14 * dt * self.hz
		elif moving:
			engine_temp += 0.05 * dt * self.hz
		else:
			engine_temp -= 0.22 * dt * self.hz
		if "MOTOR_OVERHEAT" in faults:
			engine_temp += 1.4
		self.state["traction_motor_temp_c"] = max(35.0, min(175.0, engine_temp + self._engine_temp_bias + wave * 0.35))

		brake_temp = float(self.state.get("brakes_temperature_c", 38.0))
		if mode == "braking":
			brake_temp += 0.55 + min(0.6, speed_kph / 180.0)
		elif moving:
			brake_temp -= 0.10
		else:
			brake_temp -= 0.18
		if "BRAKE_PRESSURE_DROP" in faults:
			brake_temp += 0.45
		self.state["brakes_temperature_c"] = max(24.0, min(165.0, brake_temp + self._brake_temp_bias + wave * 0.45))

		pressure = 5.0 + self._pressure_bias
		if mode == "braking":
			pressure -= 0.7
		elif mode == "traction":
			pressure -= 0.08
		if "BRAKE_PRESSURE_DROP" in faults:
			pressure -= 1.6
		self.state["brake_pipe_pressure_bar"] = max(2.2, min(5.4, pressure + wave * 0.05))

		voltage = 25.0 + self._voltage_bias
		if mode == "traction" and accel > 0.02:
			voltage -= 0.22
		if "CATENARY_VOLTAGE_SAG" in faults:
			voltage -= 8.2
		voltage_final = max(14.8, min(27.2, voltage + wave * 0.18))

		current = float(self.state.get("traction_current_a", 0.0))
		if mode == "traction" and accel > 0.05:
			current_target = 720.0 + min(380.0, speed_kph * 3.4)
		elif mode == "braking":
			current_target = 120.0 + min(120.0, speed_kph * 0.9)
		elif moving:
			current_target = 360.0 + min(180.0, speed_kph * 1.2)
		else:
			current_target = 70.0
		if "MOTOR_OVERHEAT" in faults:
			current_target += 160.0
		if "CATENARY_VOLTAGE_SAG" in faults:
			current_target += 120.0
		current += (current_target * self._current_scale - current) * 0.34
		current_final = max(0.0, min(1800.0, current + wave * 9.0))

		if self._traction_type == "electric":
			self.state["catenary_voltage_kv"] = voltage_final
			self.state["traction_current_a"] = current_final
			self.state["energy_consumption_kwh"] = round(
				float(self.state.get("energy_consumption_kwh") or 0.0)
				+ max(0.0, float(self.state.get("traction_power_kw") or 0.0)) / (self.hz * 3600.0),
				4,
			)
		else:
			self.state["catenary_voltage_kv"] = None
			self.state["traction_current_a"] = None
			self.state["traction_power_kw"] = None
			self.state["regen_power_kw"] = None
			self.state["energy_consumption_kwh"] = None

	def _synchronize_metric_aliases(self) -> None:
		self.state["traction_type"] = self._traction_type
		self.state["engine_temperature_c"] = float(self.state.get("traction_motor_temp_c", 0.0))
		self.state["pressure_bar"] = float(self.state.get("brake_pipe_pressure_bar", 0.0))
		voltage = self.state.get("catenary_voltage_kv")
		current = self.state.get("traction_current_a")
		self.state["voltage_kv"] = float(voltage) if voltage is not None else None
		self.state["current_a"] = float(current) if current is not None else None

	@staticmethod
	def _segment_index_from_label(label: str) -> int:
		try:
			return int(label.rsplit(":", 1)[-1])
		except (ValueError, IndexError):
			return 0

	# ------------------------------------------------------------------
	# Journey FSM
	# ------------------------------------------------------------------

	def _journey_target_speed(self) -> float:
		"""Return the target speed (kph) this tick and advance the FSM."""

		# ── dwell at intermediate station ──────────────────────────────
		if self._journey == _State.STOPPED:
			self._dwell_remaining -= 1
			if self._dwell_remaining <= 0:
				self._target_station_km = None	# unlock, seek next station
				self._journey = _State.RUNNING
			return 0.0

		# ── turnaround pause at terminus ───────────────────────────────
		if self._journey == _State.TERMINUS_WAIT:
			self._dwell_remaining -= 1
			if self._dwell_remaining <= 0:
				self._target_station_km = None
				self._follower.reverse()
				self._journey = _State.RUNNING
			return 0.0

		# ── RUNNING: decide target speed from position ─────────────────

		# Check terminus first (direction-aware)
		if self._follower.at_terminus():
			if float(self.state["speed_kph"]) < 1.0:
				self._journey = _State.TERMINUS_WAIT
				self._dwell_remaining = _TERMINUS_TICKS
				self._current_station_name = "terminus"
			return 0.0

		# Lock onto the next upcoming station
		if self._target_station_km is None:
			nxt = self._follower.next_station()
			if nxt is not None:
				self._target_station_km = nxt.km
				self._current_station_name = nxt.name

		if self._target_station_km is None:
			return _CRUISE_KPH

		dist = abs(self._target_station_km - self._follower.pos_km)

		# Close enough — declare stop
		if dist <= _STOP_THRESHOLD_KM:
			if float(self.state["speed_kph"]) < 3.0:
				self._journey = _State.STOPPED
				self._dwell_remaining = _DWELL_TICKS_BASE
				return 0.0
			return 0.0	# still braking to a halt

		# Crawl zone
		if dist <= _APPROACH_START_KM:
			return _APPROACH_KPH

		# Braking zone — linear ramp from cruise down to approach speed
		if dist <= _BRAKE_START_KM:
			t = (dist - _APPROACH_START_KM) / (_BRAKE_START_KM - _APPROACH_START_KM)
			return _APPROACH_KPH + t * (_CRUISE_KPH - _APPROACH_KPH)

		return _CRUISE_KPH
