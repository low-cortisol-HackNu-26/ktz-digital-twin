from __future__ import annotations


def hz_for_scenario(base_hz: int, scenario: str) -> int:
	if scenario == "burst_x10":
		return max(1, base_hz * 10)
	return max(1, base_hz)
