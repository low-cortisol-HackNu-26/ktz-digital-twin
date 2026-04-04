"""
RouteFollower — GPS movement along a KTZ railway route with stations.

Coordinate format: [lng, lat] (GeoJSON).
"""
from __future__ import annotations

import math


# ---------------------------------------------------------------------------
# Stations per route  (fraction of total route length, 0.0 = start, 1.0 = end)
# These are approximate positions of major cities/junctions on each route.
# ---------------------------------------------------------------------------
_ROUTE_STATIONS: dict[str, list[tuple[float, str]]] = {
	"ALA-NUR": [
		(0.00, "Almaty-1"),
		(0.08, "Kapchagai"),
		(0.20, "Uzynagash"),
		(0.35, "Chu"),
		(0.52, "Moyynty"),
		(0.68, "Osakarovka"),
		(0.82, "Karagandy"),
		(0.93, "Nur-Sultan-Pass"),
		(1.00, "Nur-Sultan"),
	],
	"ALA-SHY": [
		(0.00, "Almaty-1"),
		(0.15, "Otegen Batyr"),
		(0.32, "Saryozek"),
		(0.55, "Aris"),
		(0.80, "Turkestan"),
		(1.00, "Shymkent"),
	],
	"NUR-AKT": [
		(0.00, "Nur-Sultan"),
		(0.12, "Shortandy"),
		(0.28, "Kokshetau"),
		(0.45, "Petropavl-Jct"),
		(0.60, "Presnovka"),
		(0.75, "Kostanay"),
		(0.88, "Tobol"),
		(1.00, "Aktobe"),
	],
	"NUR-PET": [
		(0.00, "Nur-Sultan"),
		(0.30, "Shortandy"),
		(0.60, "Makinsk"),
		(1.00, "Petropavl"),
	],
	"SHY-KYZ": [
		(0.00, "Shymkent"),
		(0.22, "Turkestan"),
		(0.50, "Baikonur"),
		(0.75, "Zhosaly"),
		(1.00, "Kyzylorda"),
	],
}

_DEFAULT_STATIONS = [(0.0, "Start"), (1.0, "End")]


def _haversine_km(p1: list[float], p2: list[float]) -> float:
	lon1, lat1 = math.radians(p1[0]), math.radians(p1[1])
	lon2, lat2 = math.radians(p2[0]), math.radians(p2[1])
	dlat, dlon = lat2 - lat1, lon2 - lon1
	a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
	return 6371.0 * 2 * math.asin(math.sqrt(a))


class Station:
	def __init__(self, name: str, km: float) -> None:
		self.name = name
		self.km = km  # distance from route start


class RouteFollower:
	"""
	Moves a point along a polyline.  Exposes station list so the FSM
	in StateMachine can decide when to brake / stop / depart.
	"""

	def __init__(self, route: dict, start_fraction: float = 0.0) -> None:
		self.code: str = route["code"]
		self.coords: list[list[float]] = route["coordinates"]
		self.direction: int = 1

		# Cumulative distances
		self._seg_lengths: list[float] = []
		self._cum_dist: list[float] = [0.0]
		for i in range(len(self.coords) - 1):
			d = _haversine_km(self.coords[i], self.coords[i + 1])
			self._seg_lengths.append(d)
			self._cum_dist.append(self._cum_dist[-1] + d)

		self.total_km: float = self._cum_dist[-1] or float(route.get("total_length_km", 1.0))
		self._pos_km: float = start_fraction * self.total_km

		# Build station list in km
		fractions = _ROUTE_STATIONS.get(self.code, _DEFAULT_STATIONS)
		self.stations: list[Station] = [
			Station(name, frac * self.total_km) for frac, name in fractions
		]

	# ------------------------------------------------------------------
	# Read-only properties
	# ------------------------------------------------------------------

	@property
	def lat(self) -> float:
		return self._interpolate()[1]

	@property
	def lng(self) -> float:
		return self._interpolate()[0]

	@property
	def pos_km(self) -> float:
		return self._pos_km

	@property
	def segment_label(self) -> str:
		return f"{self.code}:{self._segment_index():03d}"

	@property
	def progress_fraction(self) -> float:
		return self._pos_km / self.total_km if self.total_km > 0 else 0.0

	def next_station(self) -> Station | None:
		"""Return the nearest upcoming station in the current direction."""
		if self.direction == 1:
			candidates = [s for s in self.stations if s.km > self._pos_km + 0.1]
			return candidates[0] if candidates else None
		else:
			candidates = [s for s in self.stations if s.km < self._pos_km - 0.1]
			return candidates[-1] if candidates else None

	def distance_to_next_station_km(self) -> float:
		s = self.next_station()
		if s is None:
			return float("inf")
		return abs(s.km - self._pos_km)

	def at_terminus(self) -> bool:
		"""True when we've reached the terminus in the current direction of travel."""
		if self.direction == 1:
			return self._pos_km >= self.total_km - 0.1
		return self._pos_km <= 0.1

	# ------------------------------------------------------------------
	# Movement
	# ------------------------------------------------------------------

	def advance(self, distance_km: float) -> None:
		self._pos_km += self.direction * distance_km
		if self._pos_km >= self.total_km:
			self._pos_km = self.total_km
		elif self._pos_km <= 0.0:
			self._pos_km = 0.0
		self._pos_km = max(0.0, min(self.total_km, self._pos_km))

	def reverse(self) -> None:
		self.direction *= -1

	# ------------------------------------------------------------------
	# Internals
	# ------------------------------------------------------------------

	def _segment_index(self) -> int:
		pos = self._pos_km
		for i, cum in enumerate(self._cum_dist[1:]):
			if pos <= cum:
				return i
		return max(0, len(self.coords) - 2)

	def _interpolate(self) -> list[float]:
		if not self.coords:
			return [76.9, 43.2]
		if len(self.coords) == 1:
			return list(self.coords[0])
		pos = max(0.0, min(self.total_km, self._pos_km))
		idx = self._segment_index()
		seg_start = self._cum_dist[idx]
		seg_len = self._seg_lengths[idx] if idx < len(self._seg_lengths) else 0.0
		if seg_len < 1e-9:
			return list(self.coords[idx])
		t = max(0.0, min(1.0, (pos - seg_start) / seg_len))
		p0, p1 = self.coords[idx], self.coords[min(idx + 1, len(self.coords) - 1)]
		return [p0[0] + t * (p1[0] - p0[0]), p0[1] + t * (p1[1] - p0[1])]
