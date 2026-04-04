from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from .models import LocomotiveState


@dataclass
class DeliveryPlan:
    send: bool = True
    duplicate: bool = False
    delay_sec: float = 0.0
    timestamp_shift_sec: float = 0.0


def quality_profile_for_scenario(
    scenario_name: str,
    scenario_settings: dict[str, Any],
    quality_profiles: dict[str, Any],
) -> dict[str, Any]:
    mode = scenario_settings.get(scenario_name, {}).get("quality_mode", "clean")
    return dict(quality_profiles.get(mode, quality_profiles.get("clean", {})))


def _jitter_gps(lat: float, lon: float, meters: float, rng: random.Random) -> tuple[float, float]:
    if meters <= 0:
        return lat, lon
    # Rough conversion for small perturbations.
    dlat = rng.uniform(-meters, meters) / 111_320.0
    dlon = rng.uniform(-meters, meters) / max(1.0, 80_000.0)
    return lat + dlat, lon + dlon


def apply_quality_to_payload(
    state: LocomotiveState,
    payload: dict[str, Any],
    profile: dict[str, Any],
    rng: random.Random,
) -> tuple[dict[str, Any], DeliveryPlan]:
    plan = DeliveryPlan()

    if rng.random() < float(profile.get("drop_prob", 0.0)):
        plan.send = False
        return payload, plan

    if rng.random() < float(profile.get("duplicate_prob", 0.0)):
        plan.duplicate = True

    if rng.random() < float(profile.get("out_of_order_prob", 0.0)):
        plan.timestamp_shift_sec = -rng.uniform(0.2, 2.2)

    if rng.random() < float(profile.get("delay_prob", 0.0)):
        plan.delay_sec = float(profile.get("delay_sec", 0.0))

    # Sensor freeze keeps speed and acceleration stale for several ticks.
    if state.freeze_ticks_left > 0:
        payload["speed_kph"] = state.frozen_speed_kph
        payload["acceleration"] = 0.0
        state.freeze_ticks_left -= 1
    elif rng.random() < float(profile.get("sensor_freeze_prob", 0.0)):
        state.freeze_ticks_left = rng.randint(2, 8)
        state.frozen_speed_kph = float(payload.get("speed_kph", 0.0))

    # Optional field dropout (contract-safe fields only).
    if rng.random() < float(profile.get("missing_optional_prob", 0.0)):
        for name in ("target_speed_kph", "allowed_speed_kph", "gps_lat", "gps_lon"):
            if rng.random() < 0.5:
                payload[name] = None

    # GPS jitter and temperature noise.
    gps_jitter_m = float(profile.get("gps_jitter_m", 0.0))
    if payload.get("gps_lat") is not None and payload.get("gps_lon") is not None:
        lat, lon = _jitter_gps(float(payload["gps_lat"]), float(payload["gps_lon"]), gps_jitter_m, rng)
        payload["gps_lat"] = lat
        payload["gps_lon"] = lon

    temp_noise = float(profile.get("temp_noise_c", 0.0))
    for tfield in ("transformer_temp_c", "converter_temp_c", "traction_motor_temp_c", "axle_bearing_temp_c"):
        payload[tfield] = max(-60.0, float(payload[tfield]) + rng.uniform(-temp_noise, temp_noise))

    # Degrade quality indicators coherently with profile severity.
    severity = min(0.9, float(profile.get("drop_prob", 0.0)) + float(profile.get("delay_prob", 0.0)))
    payload["signal_quality"] = max(0.0, min(1.0, float(payload["signal_quality"]) - severity * 0.25))
    payload["data_quality"] = max(0.0, min(1.0, float(payload["data_quality"]) - severity * 0.35))

    if plan.timestamp_shift_sec != 0.0:
        shifted = state.simulation_time + timedelta(seconds=plan.timestamp_shift_sec)
        payload["timestamp"] = shifted.isoformat()

    return payload, plan


async def publish_with_plan(
    post_event,
    payload: dict[str, Any],
    ingest_url: str,
    plan: DeliveryPlan,
) -> None:
    if not plan.send:
        return

    if plan.delay_sec > 0:
        await asyncio.sleep(plan.delay_sec)

    await post_event(ingest_url, payload)
    if plan.duplicate:
        await post_event(ingest_url, payload)
