from __future__ import annotations

import asyncio
import json
import os
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()


@dataclass
class SimState:
    locomotive_id: str
    speed_kph: float = 0.0
    traction_power_kw: float = 0.0
    brake_pipe_pressure_bar: float = 5.0
    traction_motor_temp_c: float = 45.0
    converter_temp_c: float = 40.0
    transformer_temp_c: float = 42.0
    axle_bearing_temp_c: float = 35.0
    vibration_gearbox: float = 2.0
    lat: float = 43.2389
    lon: float = 76.8897
    step: int = 0


def read_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


def clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def create_event(state: SimState, anomalies: dict[str, bool], schema_version: str) -> dict:
    phase = (state.step % 200) / 200.0

    target_speed = 80.0 + 20.0 * (0.5 - abs(phase - 0.5))
    speed_delta = (target_speed - state.speed_kph) * 0.08 + random.uniform(-0.8, 0.8)
    state.speed_kph = clip(state.speed_kph + speed_delta, 0.0, 180.0)

    traction_mode = "traction"
    if speed_delta < -0.3:
        traction_mode = "braking"
    if abs(speed_delta) < 0.15:
        traction_mode = "coast"

    state.traction_power_kw = clip(state.speed_kph * 18.0 + random.uniform(-120, 120), 0, 9000)
    regen_power_kw = 0.0
    tractive_effort_kn = clip(state.traction_power_kw / 20.0, 0, 650)

    if traction_mode == "braking":
        regen_power_kw = clip(abs(speed_delta) * 900 + random.uniform(0, 150), 0, 3500)
        tractive_effort_kn = -clip(regen_power_kw / 18.0, 0, 420)

    state.brake_pipe_pressure_bar = clip(
        5.0 - (0.9 if traction_mode == "braking" else 0.0) + random.uniform(-0.05, 0.05),
        2.5,
        5.3,
    )

    catenary_voltage_kv = clip(25.0 + random.uniform(-1.2, 1.2), 18.0, 28.0)
    traction_current_a = clip((state.traction_power_kw * 1000) / (catenary_voltage_kv * 1000 + 1), -4500, 4500)

    state.traction_motor_temp_c = clip(state.traction_motor_temp_c + state.traction_power_kw / 30000 - 0.05, 30, 160)
    state.converter_temp_c = clip(state.converter_temp_c + state.traction_power_kw / 45000 - 0.04, 28, 140)
    state.transformer_temp_c = clip(state.transformer_temp_c + state.traction_power_kw / 50000 - 0.03, 30, 140)
    state.axle_bearing_temp_c = clip(state.axle_bearing_temp_c + state.speed_kph / 6000 - 0.01, 25, 120)

    state.vibration_gearbox = clip(1.5 + state.speed_kph / 70 + random.uniform(-0.4, 0.4), 0.4, 12.0)

    active_fault_codes: list[str] = []

    if anomalies.get("overspeed"):
        state.speed_kph = clip(state.speed_kph + 40.0, 0.0, 220.0)
        active_fault_codes.append("SPD_OVR")
    if anomalies.get("brake_pressure_drop"):
        state.brake_pipe_pressure_bar = clip(state.brake_pipe_pressure_bar - 2.5, 0.0, 5.0)
        active_fault_codes.append("BRK_P_DROP")
    if anomalies.get("motor_overheat"):
        state.traction_motor_temp_c = clip(state.traction_motor_temp_c + 50.0, 0.0, 250.0)
        state.converter_temp_c = clip(state.converter_temp_c + 25.0, 0.0, 220.0)
        active_fault_codes.append("MTR_TMP_HI")
    if anomalies.get("catenary_voltage_sag"):
        catenary_voltage_kv = clip(catenary_voltage_kv - 8.0, 0.0, 28.0)
        active_fault_codes.append("CAT_SAG")
    if anomalies.get("gearbox_vibration_high"):
        state.vibration_gearbox = clip(state.vibration_gearbox + 15.0, 0.0, 60.0)
        active_fault_codes.append("GBX_VIB_HI")

    state.lat += random.uniform(-0.0003, 0.0003)
    state.lon += random.uniform(-0.0003, 0.0003)

    signal_quality = clip(0.95 + random.uniform(-0.1, 0.03), 0.0, 1.0)
    data_quality = clip(0.97 + random.uniform(-0.07, 0.02), 0.0, 1.0)

    if anomalies.get("catenary_voltage_sag"):
        data_quality = clip(data_quality - 0.2, 0.0, 1.0)

    event = {
        "timestamp": datetime.now(UTC).isoformat(),
        "locomotive_id": state.locomotive_id,
        "speed_kph": round(state.speed_kph, 3),
        "target_speed_kph": round(target_speed, 3),
        "allowed_speed_kph": 120.0,
        "acceleration": round(speed_delta, 4),
        "traction_mode": "regen" if regen_power_kw > 100 else traction_mode,
        "tractive_effort_kn": round(tractive_effort_kn, 3),
        "brake_pipe_pressure_bar": round(state.brake_pipe_pressure_bar, 4),
        "brake_cylinder_pressure_bar": round(0.4 if traction_mode != "braking" else 3.5, 4),
        "pantograph_up": True,
        "catenary_voltage_kv": round(catenary_voltage_kv, 4),
        "traction_current_a": round(traction_current_a, 3),
        "traction_power_kw": round(state.traction_power_kw, 3),
        "regen_power_kw": round(regen_power_kw, 3),
        "transformer_temp_c": round(state.transformer_temp_c, 3),
        "converter_temp_c": round(state.converter_temp_c, 3),
        "traction_motor_temp_c": round(state.traction_motor_temp_c, 3),
        "axle_bearing_temp_c": round(state.axle_bearing_temp_c, 3),
        "compressor_state": "on" if state.brake_pipe_pressure_bar < 4.8 else "off",
        "compressor_cycles_per_hour": 22.0,
        "pneumatic_pressure_bar": round(8.2 + random.uniform(-0.2, 0.2), 3),
        "vibration_motor": round(1.0 + state.speed_kph / 100 + random.uniform(-0.3, 0.3), 3),
        "vibration_gearbox": round(state.vibration_gearbox, 3),
        "gps_lat": round(state.lat, 6),
        "gps_lon": round(state.lon, 6),
        "route_segment": "ALM-01",
        "gradient_permille": round(random.uniform(-8.0, 8.0), 2),
        "train_mass_tons": 4200.0,
        "active_fault_codes": active_fault_codes,
        "signal_quality": round(signal_quality, 3),
        "data_quality": round(data_quality, 3),
        "source": "simulator",
        "schema_version": schema_version,
    }

    state.step += 1
    return event


async def run() -> None:
    config_path = Path(os.getenv("SIMULATOR_CONFIG_PATH", "/app/config.json"))
    backend_ingest = os.getenv("SIMULATOR_INGEST_URL", "http://backend:8000/api/ingest/telemetry")
    schema_version = os.getenv("SCHEMA_VERSION", "1.0.0")

    boot = read_config(config_path)
    hz = float(os.getenv("SIMULATOR_HZ", boot.get("hz", 5)))
    hz = max(5.0, min(10.0, hz))

    locomotive_ids = boot.get("locomotives", [os.getenv("SIMULATOR_LOCOMOTIVE_ID", "KZ8A-0001")])
    states = [SimState(locomotive_id=loc_id) for loc_id in locomotive_ids]

    async with httpx.AsyncClient(timeout=5.0) as client:
        while True:
            cfg = read_config(config_path)
            anomalies = cfg.get("anomalies", {})

            batch = [create_event(state, anomalies, schema_version) for state in states]
            try:
                response = await client.post(backend_ingest, json=batch)
                response.raise_for_status()
            except Exception as exc:
                print(f"simulator ingest failed: {exc}")

            await asyncio.sleep(1.0 / hz)


if __name__ == "__main__":
    asyncio.run(run())
