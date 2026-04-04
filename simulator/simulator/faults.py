from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import LocomotiveState

_PHASES = ("onset", "developing", "warning", "critical", "recovery")


@dataclass
class ScenarioThresholds:
    onset_sec: float
    developing_sec: float
    warning_sec: float
    critical_sec: float
    recovery_sec: float

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> "ScenarioThresholds":
        return cls(
            onset_sec=float(settings.get("onset_sec", 20.0)),
            developing_sec=float(settings.get("developing_sec", 40.0)),
            warning_sec=float(settings.get("warning_sec", 60.0)),
            critical_sec=float(settings.get("critical_sec", 90.0)),
            recovery_sec=float(settings.get("recovery_sec", 130.0)),
        )


def _phase_for_elapsed(elapsed: float, th: ScenarioThresholds) -> str:
    if elapsed < th.developing_sec:
        return "onset"
    if elapsed < th.warning_sec:
        return "developing"
    if elapsed < th.critical_sec:
        return "warning"
    if elapsed < th.recovery_sec:
        return "critical"
    return "recovery"


def _severity(phase: str) -> float:
    return {
        "onset": 0.25,
        "developing": 0.45,
        "warning": 0.70,
        "critical": 1.00,
        "recovery": 0.35,
    }.get(phase, 0.0)


def apply_progressive_faults(
    state: LocomotiveState,
    dt_sec: float,
    scenario_name: str,
    scenario_settings: dict[str, Any],
) -> None:
    state.scenario.total_elapsed_sec += dt_sec
    thresholds = ScenarioThresholds.from_settings(scenario_settings)
    phase = _phase_for_elapsed(state.scenario.total_elapsed_sec, thresholds)
    state.scenario.phase = phase

    sev = _severity(phase)
    faults: list[str] = []

    if scenario_name == "normal" or scenario_name == "burst_x10":
        state.active_fault_codes = []
        return

    if scenario_name == "overspeed":
        state.target_speed_kph = max(state.target_speed_kph, state.allowed_speed_kph + 8 + 15 * sev)
        if phase in {"warning", "critical"}:
            state.brake_cylinder_pressure_bar = min(state.brake_cylinder_pressure_bar, 0.25)
        if state.speed_kph > state.allowed_speed_kph + 2:
            faults.append("OVERSPEED")

    if scenario_name == "brake_pressure_drop":
        state.pneumatic_pressure_bar = max(4.3, state.pneumatic_pressure_bar - 0.06 * sev)
        state.brake_pipe_pressure_bar = max(2.2, state.brake_pipe_pressure_bar - 0.07 * sev)
        state.compressor_state = "on"
        state.compressor_cycles_per_hour = min(52.0, state.compressor_cycles_per_hour + 0.5)
        if sev >= 0.45:
            faults.append("BRAKE_PRESSURE_DROP")

    if scenario_name == "motor_overheat":
        state.thermal.traction_motor_temp_c += 0.9 * sev
        state.thermal.transformer_temp_c += 0.4 * sev
        state.traction_current_a *= 1.0 + 0.05 * sev
        if sev >= 0.45:
            faults.append("MOTOR_OVERHEAT")
        if phase == "critical":
            state.throttle_cmd *= 0.8

    if scenario_name == "converter_overheat":
        state.thermal.converter_temp_c += 1.0 * sev
        state.thermal.transformer_temp_c += 0.35 * sev
        if sev >= 0.45:
            faults.append("CONVERTER_OVERHEAT")
        if phase == "critical":
            state.throttle_cmd *= 0.82

    if scenario_name == "catenary_voltage_sag":
        state.catenary_voltage_kv = max(12.0, state.catenary_voltage_kv * (1.0 - 0.24 * sev))
        state.traction_current_a *= 1.0 + 0.22 * sev
        state.traction_power_kw *= 1.0 - 0.18 * sev
        state.tractive_effort_kn *= 1.0 - 0.22 * sev
        state.target_speed_kph = max(state.target_speed_kph, state.speed_kph + 16.0)
        if sev >= 0.45:
            faults.append("CATENARY_VOLTAGE_SAG")

    if scenario_name == "gearbox_vibration_high":
        state.vibration_gearbox += 1.2 * sev + 0.02 * state.speed_kph
        state.vibration_motor += 0.5 * sev
        if sev >= 0.45:
            faults.append("GEARBOX_VIBRATION_HIGH")

    if scenario_name == "signal_quality_loss":
        state.signal_quality = max(0.05, state.signal_quality - 0.12 * sev)
        state.data_quality = max(0.05, state.data_quality - 0.09 * sev)
        if sev >= 0.45:
            faults.append("SIGNAL_QUALITY_LOSS")

    if scenario_name == "stale_telemetry":
        state.signal_quality = max(0.1, state.signal_quality - 0.10 * sev)
        state.data_quality = max(0.1, state.data_quality - 0.08 * sev)
        if sev >= 0.45:
            faults.append("STALE_TELEMETRY")

    if scenario_name == "repeated_fault_codes":
        faults.extend(["INTERMITTENT_CTRL_FAULT", "INTERMITTENT_CTRL_FAULT"])
        if phase in {"warning", "critical"}:
            faults.append("INTERMITTENT_BRAKE_FEEDBACK")

    # Natural coupling between signal and data quality.
    state.signal_quality = max(0.0, min(1.0, state.signal_quality))
    state.data_quality = max(0.0, min(1.0, min(state.data_quality, state.signal_quality + 0.05)))

    # Deduplicate while keeping stable order.
    seen: set[str] = set()
    ordered_faults: list[str] = []
    for code in faults:
        if code not in seen:
            seen.add(code)
            ordered_faults.append(code)
    state.active_fault_codes = ordered_faults
