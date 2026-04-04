from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SegmentContext:
	allowed_speed_kph: float
	track_condition: str
	weather_condition: str


_DEMO_PROFILE: list[SegmentContext] = [
	SegmentContext(allowed_speed_kph=80.0, track_condition="normal", weather_condition="clear"),
	SegmentContext(allowed_speed_kph=60.0, track_condition="rough", weather_condition="rain"),
	SegmentContext(allowed_speed_kph=40.0, track_condition="bad", weather_condition="fog"),
	SegmentContext(allowed_speed_kph=70.0, track_condition="normal", weather_condition="clear"),
	SegmentContext(allowed_speed_kph=55.0, track_condition="maintenance_zone", weather_condition="wind"),
	SegmentContext(allowed_speed_kph=50.0, track_condition="rough", weather_condition="snow"),
]


def context_for_segment(segment_index: int, distance_to_station_km: float) -> SegmentContext:
	if distance_to_station_km <= 0.25:
		return SegmentContext(
			allowed_speed_kph=20.0,
			track_condition="normal",
			weather_condition="clear",
		)

	if segment_index < 0:
		segment_index = 0

	return _DEMO_PROFILE[segment_index % len(_DEMO_PROFILE)]
