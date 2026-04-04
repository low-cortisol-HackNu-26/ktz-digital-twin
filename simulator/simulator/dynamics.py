from __future__ import annotations
from random import Random

from .models import LocomotiveState


def choose_operational_mode(state: LocomotiveState, station_approach: bool) -> str:
    if state.speed_kph < 0.8 and station_approach:
        return "station_stop"
    if state.speed_kph < 2.0:
        return "departure"
    if station_approach and state.speed_kph > 8.0:
        return "braking"
    if state.speed_kph < state.target_speed_kph - 5:
        return "acceleration"
    if abs(state.speed_kph - state.target_speed_kph) <= 3:
        return "cruise"
    if state.speed_kph > state.allowed_speed_kph + 1:
        return "braking"
    if state.speed_kph > state.target_speed_kph + 3:
        return "coasting"
    return "coasting"


def update_motion_and_power(state: LocomotiveState, dt: float, rng: Random) -> None:
    # Speed target follows infrastructure limits with operational margin.
    state.target_speed_kph = max(0.0, state.allowed_speed_kph * 0.94)

    if state.operational_mode in {"departure", "acceleration"}:
        state.traction_mode = "traction"
        state.throttle_cmd = min(1.0, 0.40 + (state.target_speed_kph - state.speed_kph) / 90.0)
        state.braking_cmd = 0.0
    elif state.operational_mode == "cruise":
        state.traction_mode = "coast"
        state.throttle_cmd = 0.25
        state.braking_cmd = 0.0
    elif state.operational_mode == "coasting":
        state.traction_mode = "coast"
        state.throttle_cmd = 0.05
        state.braking_cmd = 0.05
    elif state.operational_mode == "braking":
        state.traction_mode = "regen" if state.speed_kph > 12 else "braking"
        state.throttle_cmd = 0.0
        state.braking_cmd = min(1.0, 0.35 + state.speed_kph / 140.0)
    else:
        state.traction_mode = "coast"
        state.throttle_cmd = 0.0
        state.braking_cmd = 0.0

    mass_kg = max(100_000.0, state.train_mass_tons * 1000.0)

    # KZ8A-class traction envelope (simplified): enough force to start heavy consist on moderate grades.
    traction_force_n = state.throttle_cmd * 5_100_000.0 * state.adhesion_factor
    brake_force_n = state.braking_cmd * 2_200_000.0

    speed_mps = state.speed_kph / 3.6
    # Rolling resistance ~0.12% of weight for rail, plus quadratic aerodynamic drag.
    rolling_n = 0.0012 * mass_kg * 9.81
    aero_n = 2.0 * speed_mps * speed_mps
    grade_n = mass_kg * 9.81 * (state.gradient_permille / 1000.0)

    net_force_n = traction_force_n - brake_force_n - rolling_n - aero_n - grade_n
    accel = net_force_n / mass_kg

    new_speed = max(0.0, state.speed_kph + accel * dt * 3.6)
    state.acceleration = (new_speed - state.speed_kph) / dt / 3.6
    state.speed_kph = new_speed

    state.tractive_effort_kn = max(0.0, traction_force_n / 1000.0)
    state.traction_power_kw = max(0.0, (traction_force_n * (state.speed_kph / 3.6)) / 1000.0)

    if state.traction_mode == "regen":
        state.regen_power_kw = min(2800.0, (brake_force_n * speed_mps) / 1000.0 * 0.35)
    else:
        state.regen_power_kw = 0.0

    state.traction_current_a = max(
        0.0,
        (state.traction_power_kw * 1000.0) / max(18_000.0, state.catenary_voltage_kv * 1000.0),
    )

    state.brake_pipe_pressure_bar = max(2.0, 5.2 - state.braking_cmd * 2.8)
    state.brake_cylinder_pressure_bar = min(5.2, 0.2 + state.braking_cmd * 3.8)

    # Pneumatic dynamics with compressor hysteresis.
    state.pneumatic_pressure_bar = max(5.0, min(9.2, state.pneumatic_pressure_bar - state.braking_cmd * 0.24 + state.throttle_cmd * 0.02))
    if state.pneumatic_pressure_bar < 7.0:
        state.compressor_state = "on"
    elif state.pneumatic_pressure_bar > 8.2:
        state.compressor_state = "off"

    if state.compressor_state == "on":
        state.pneumatic_pressure_bar = min(8.8, state.pneumatic_pressure_bar + 0.16)
        state.compressor_cycles_per_hour = min(38.0, state.compressor_cycles_per_hour + 0.6)
    else:
        state.compressor_cycles_per_hour = max(4.0, state.compressor_cycles_per_hour - 0.12)

    vibration_load = 0.006 * state.speed_kph + 0.0008 * state.tractive_effort_kn
    random_noise = rng.uniform(-0.03, 0.03)
    state.vibration_motor = max(0.0, state.vibration_baseline + vibration_load + random_noise)
    state.vibration_gearbox = max(0.0, state.vibration_baseline * 0.9 + vibration_load * 1.15 + state.gearbox_wear_factor + random_noise)


def update_thermal(state: LocomotiveState, dt: float, thermal_inertia: float, cooling_factor: float) -> None:
    def step(temp: float, heat_kw: float, load_bias: float, ambient: float = 28.0) -> float:
        heating = heat_kw * load_bias
        cooling = max(0.0, (temp - ambient) * cooling_factor)
        delta = (heating - cooling) * thermal_inertia * dt
        return max(ambient, temp + delta)

    traction_heat = state.traction_power_kw / 1500.0
    regen_heat_relief = state.regen_power_kw / 2400.0

    state.thermal.transformer_temp_c = step(
        state.thermal.transformer_temp_c,
        max(0.0, traction_heat - regen_heat_relief * 0.25),
        load_bias=0.16,
    )
    state.thermal.converter_temp_c = step(
        state.thermal.converter_temp_c,
        max(0.0, traction_heat - regen_heat_relief * 0.2),
        load_bias=0.18,
    )
    state.thermal.traction_motor_temp_c = step(
        state.thermal.traction_motor_temp_c,
        max(0.0, traction_heat + 0.12 * state.tractive_effort_kn / 100.0),
        load_bias=0.22,
    )
    state.thermal.axle_bearing_temp_c = step(
        state.thermal.axle_bearing_temp_c,
        max(0.0, state.speed_kph / 110.0 + state.vibration_gearbox / 3.0),
        load_bias=0.14,
    )


def sync_public_thermal_fields(state: LocomotiveState) -> None:
    state.transformer_temp_c = state.thermal.transformer_temp_c
    state.converter_temp_c = state.thermal.converter_temp_c
    state.traction_motor_temp_c = state.thermal.traction_motor_temp_c
    state.axle_bearing_temp_c = state.thermal.axle_bearing_temp_c
