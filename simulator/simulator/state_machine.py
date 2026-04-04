from __future__ import annotations

import json
from copy import deepcopy
from enum import Enum, auto
from pathlib import Path
from typing import Any

from .packets import DEFAULT_INITIAL_STATE, build_packet
from .route_follower import RouteFollower
from .scenarios.anomaly import apply_fault
from .scenarios.normal import update_physics

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

		# Prime GPS
		self.state["gps_lat"] = self._follower.lat
		self.state["gps_lon"] = self._follower.lng
		self.state["route_segment"] = self._follower.segment_label

	# ------------------------------------------------------------------

	def next_packet(self) -> dict[str, Any]:
		self.tick += 1

		target_speed = self._journey_target_speed()

		self.state = update_physics(self.state, target_speed, self.hz)

		if self.scenario in {
			"overspeed", "brake_pressure_drop", "motor_overheat",
			"catenary_voltage_sag", "gearbox_vibration_high",
		}:
			self.state = apply_fault(self.state, self.scenario)

		# Advance GPS only while moving
		speed_kph = float(self.state["speed_kph"])
		if speed_kph > 0.1:
			distance_km = speed_kph / (self.hz * 3600.0)
			self._follower.advance(distance_km)

		self.state["gps_lat"] = self._follower.lat
		self.state["gps_lon"] = self._follower.lng
		self.state["route_segment"] = self._follower.segment_label

		return build_packet(self.locomotive_id, self.state)

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
