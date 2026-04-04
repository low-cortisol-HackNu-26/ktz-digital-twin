from __future__ import annotations

from copy import deepcopy
from typing import Any

from .packets import DEFAULT_INITIAL_STATE, build_packet
from .scenarios.anomaly import apply_fault
from .scenarios.normal import update_state


class StateMachine:
	def __init__(self, locomotive_id: str, scenario: str, hz: int) -> None:
		self.locomotive_id = locomotive_id
		self.scenario = scenario
		self.hz = max(1, hz)
		self.tick = 0
		self.state: dict[str, Any] = deepcopy(DEFAULT_INITIAL_STATE)

	def next_packet(self) -> dict[str, Any]:
		self.tick += 1
		self.state = update_state(self.state, self.tick, self.hz)

		if self.scenario in {
			"overspeed",
			"brake_pressure_drop",
			"motor_overheat",
			"catenary_voltage_sag",
			"gearbox_vibration_high",
		}:
			self.state = apply_fault(self.state, self.scenario)

		return build_packet(self.locomotive_id, self.state)
