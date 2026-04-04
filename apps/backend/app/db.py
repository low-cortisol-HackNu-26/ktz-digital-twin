from __future__ import annotations

from contextlib import asynccontextmanager
import json
from time import perf_counter
from typing import Any

import asyncpg

from .config import settings
from .metrics import metrics

_pool: asyncpg.Pool | None = None


INIT_SQL = """
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS locomotives (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS telemetry_events (
    timestamp TIMESTAMPTZ NOT NULL,
    locomotive_id TEXT NOT NULL,
    speed_kph DOUBLE PRECISION NOT NULL,
    target_speed_kph DOUBLE PRECISION NULL,
    allowed_speed_kph DOUBLE PRECISION NULL,
    acceleration DOUBLE PRECISION NULL,
    traction_mode TEXT NOT NULL,
    tractive_effort_kn DOUBLE PRECISION NULL,
    brake_pipe_pressure_bar DOUBLE PRECISION NULL,
    brake_cylinder_pressure_bar DOUBLE PRECISION NULL,
    pantograph_up BOOLEAN NOT NULL,
    catenary_voltage_kv DOUBLE PRECISION NULL,
    traction_current_a DOUBLE PRECISION NULL,
    traction_power_kw DOUBLE PRECISION NULL,
    regen_power_kw DOUBLE PRECISION NULL,
    transformer_temp_c DOUBLE PRECISION NULL,
    converter_temp_c DOUBLE PRECISION NULL,
    traction_motor_temp_c DOUBLE PRECISION NULL,
    axle_bearing_temp_c DOUBLE PRECISION NULL,
    compressor_state TEXT NULL,
    compressor_cycles_per_hour DOUBLE PRECISION NULL,
    pneumatic_pressure_bar DOUBLE PRECISION NULL,
    vibration_motor DOUBLE PRECISION NULL,
    vibration_gearbox DOUBLE PRECISION NULL,
    gps_lat DOUBLE PRECISION NULL,
    gps_lon DOUBLE PRECISION NULL,
    route_segment TEXT NULL,
    gradient_permille DOUBLE PRECISION NULL,
    train_mass_tons DOUBLE PRECISION NULL,
    active_fault_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
    signal_quality DOUBLE PRECISION NULL,
    data_quality DOUBLE PRECISION NULL,
    ingestion_time TIMESTAMPTZ NOT NULL,
    source TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    raw_payload JSONB NOT NULL,
    PRIMARY KEY (locomotive_id, timestamp)
);

SELECT create_hypertable('telemetry_events', 'timestamp', if_not_exists => TRUE, migrate_data => TRUE);

CREATE INDEX IF NOT EXISTS idx_telemetry_loco_ts_desc
ON telemetry_events (locomotive_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS current_snapshots (
    locomotive_id TEXT PRIMARY KEY,
    last_event_timestamp TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ingestion_stats (
    id SMALLINT PRIMARY KEY DEFAULT 1,
    valid_events_count BIGINT NOT NULL DEFAULT 0,
    invalid_events_count BIGINT NOT NULL DEFAULT 0,
    dropped_events_count BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ingestion_stats_singleton CHECK (id = 1)
);

INSERT INTO ingestion_stats (id)
VALUES (1)
ON CONFLICT (id) DO NOTHING;
"""


async def connect_db() -> None:
    global _pool
    _pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=20)
    async with _pool.acquire() as conn:
        await conn.execute(INIT_SQL)


async def close_db() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool is not initialized")
    return _pool


@asynccontextmanager
async def transaction():
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            yield conn


async def persist_events(events: list[dict[str, Any]]) -> None:
    if not events:
        return

    started = perf_counter()
    async with transaction() as conn:
        await conn.executemany(
            """
            INSERT INTO locomotives (id, updated_at)
            VALUES ($1, NOW())
            ON CONFLICT (id) DO UPDATE SET updated_at = NOW();
            """,
            [(evt["locomotive_id"],) for evt in events],
        )

        await conn.executemany(
            """
            INSERT INTO telemetry_events (
                timestamp, locomotive_id, speed_kph, target_speed_kph, allowed_speed_kph,
                acceleration, traction_mode, tractive_effort_kn, brake_pipe_pressure_bar,
                brake_cylinder_pressure_bar, pantograph_up, catenary_voltage_kv, traction_current_a,
                traction_power_kw, regen_power_kw, transformer_temp_c, converter_temp_c,
                traction_motor_temp_c, axle_bearing_temp_c, compressor_state,
                compressor_cycles_per_hour, pneumatic_pressure_bar, vibration_motor,
                vibration_gearbox, gps_lat, gps_lon, route_segment, gradient_permille,
                train_mass_tons, active_fault_codes, signal_quality, data_quality,
                ingestion_time, source, schema_version, raw_payload
            ) VALUES (
                $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,
                $20,$21,$22,$23,$24,$25,$26,$27,$28,$29,$30::jsonb,$31,$32,$33,$34,$35,$36::jsonb
            )
            ON CONFLICT (locomotive_id, timestamp) DO NOTHING;
            """,
            [
                (
                    evt["timestamp"], evt["locomotive_id"], evt["speed_kph"], evt.get("target_speed_kph"),
                    evt.get("allowed_speed_kph"), evt.get("acceleration"), evt["traction_mode"],
                    evt.get("tractive_effort_kn"), evt.get("brake_pipe_pressure_bar"),
                    evt.get("brake_cylinder_pressure_bar"), evt["pantograph_up"],
                    evt.get("catenary_voltage_kv"), evt.get("traction_current_a"),
                    evt.get("traction_power_kw"), evt.get("regen_power_kw"), evt.get("transformer_temp_c"),
                    evt.get("converter_temp_c"), evt.get("traction_motor_temp_c"),
                    evt.get("axle_bearing_temp_c"), evt.get("compressor_state"),
                    evt.get("compressor_cycles_per_hour"), evt.get("pneumatic_pressure_bar"),
                    evt.get("vibration_motor"), evt.get("vibration_gearbox"), evt.get("gps_lat"),
                    evt.get("gps_lon"), evt.get("route_segment"), evt.get("gradient_permille"),
                    evt.get("train_mass_tons"), json.dumps(evt.get("active_fault_codes", [])), evt.get("signal_quality"),
                    evt.get("data_quality"), evt["ingestion_time"], evt["source"], evt["schema_version"], json.dumps(evt, default=str),
                )
                for evt in events
            ],
        )

        await conn.executemany(
            """
            INSERT INTO current_snapshots (locomotive_id, last_event_timestamp, payload, updated_at)
            VALUES ($1, $2, $3::jsonb, NOW())
            ON CONFLICT (locomotive_id)
            DO UPDATE SET
                last_event_timestamp = EXCLUDED.last_event_timestamp,
                payload = EXCLUDED.payload,
                updated_at = NOW()
            WHERE current_snapshots.last_event_timestamp <= EXCLUDED.last_event_timestamp;
            """,
            [(evt["locomotive_id"], evt["timestamp"], json.dumps(evt, default=str)) for evt in events],
        )

        await conn.execute(
            """
            UPDATE ingestion_stats
            SET valid_events_count = valid_events_count + $1,
                updated_at = NOW()
            WHERE id = 1;
            """,
            len(events),
        )

    metrics.db_write_latency_ms = (perf_counter() - started) * 1000


async def increment_invalid_events(count: int) -> None:
    if count <= 0:
        return
    async with transaction() as conn:
        await conn.execute(
            """
            UPDATE ingestion_stats
            SET invalid_events_count = invalid_events_count + $1,
                updated_at = NOW()
            WHERE id = 1;
            """,
            count,
        )


async def increment_dropped_events(count: int) -> None:
    if count <= 0:
        return
    async with transaction() as conn:
        await conn.execute(
            """
            UPDATE ingestion_stats
            SET dropped_events_count = dropped_events_count + $1,
                updated_at = NOW()
            WHERE id = 1;
            """,
            count,
        )


async def fetch_locomotives() -> list[dict[str, Any]]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, created_at, updated_at
            FROM locomotives
            ORDER BY id;
            """
        )
    return [dict(row) for row in rows]


async def fetch_current_snapshot(locomotive_id: str) -> dict[str, Any] | None:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT locomotive_id, last_event_timestamp, payload, updated_at
            FROM current_snapshots
            WHERE locomotive_id = $1;
            """,
            locomotive_id,
        )
    if not row:
        return None

    snapshot = dict(row)
    payload = snapshot.get("payload")
    if isinstance(payload, str):
        snapshot["payload"] = json.loads(payload)
    return snapshot


async def fetch_history(locomotive_id: str, from_ts, to_ts, limit: int) -> list[dict[str, Any]]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT raw_payload
            FROM telemetry_events
            WHERE locomotive_id = $1
              AND ($2::timestamptz IS NULL OR timestamp >= $2)
              AND ($3::timestamptz IS NULL OR timestamp <= $3)
            ORDER BY timestamp DESC
            LIMIT $4;
            """,
            locomotive_id,
            from_ts,
            to_ts,
            limit,
        )
    events: list[dict[str, Any]] = []
    for row in rows:
        raw = row["raw_payload"]
        if isinstance(raw, str):
            events.append(json.loads(raw))
        else:
            events.append(dict(raw))
    return events


async def fetch_latest_metrics(locomotive_id: str, fields: list[str]) -> dict[str, Any] | None:
    snap = await fetch_current_snapshot(locomotive_id)
    if not snap:
        return None
    payload = snap["payload"]
    return {"locomotive_id": locomotive_id, "timestamp": snap["last_event_timestamp"], **{f: payload.get(f) for f in fields}}


async def fetch_ingestion_stats() -> dict[str, Any]:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT valid_events_count, invalid_events_count, dropped_events_count, updated_at
            FROM ingestion_stats
            WHERE id = 1;
            """
        )
    return dict(row) if row else {}
