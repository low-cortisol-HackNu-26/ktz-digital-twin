import type { TelemetryHistoryRow } from "@/lib/telemetryApi";

export const TREND_WINDOW_MIN = 15;

/** Backend validator ranges (telemetry schema) — drop obvious unit bugs / outliers from trends. */
const TEMP_MIN_C = -60;
const TEMP_MAX_C = 220;
const PRESSURE_MAX_BAR = 16;
const VOLTAGE_MAX_KV = 35;
const CURRENT_MAX_A = 5000;
const ENERGY_MAX_KWH = 50_000;

export type TrendPoint = { m: number; v: number };

function clamp(n: number, lo: number, hi: number): number {
  return Math.min(Math.max(n, lo), hi);
}

export function isElectricTraction(
  t: string | undefined | null,
): boolean {
  return (t ?? "electric").toLowerCase() === "electric";
}

export function maxDriveTempFromRow(row: TelemetryHistoryRow): number | null {
  const tt = row.traction_type ?? "electric";
  if (tt === "diesel" || tt === "fuel") {
    if (typeof row.engine_temperature_c === "number" && !Number.isNaN(row.engine_temperature_c)) {
      const t = row.engine_temperature_c;
      if (t < TEMP_MIN_C || t > TEMP_MAX_C) return null;
      return t;
    }
  }
  const vals = [row.transformer_temp_c, row.converter_temp_c, row.traction_motor_temp_c].filter(
    (x): x is number => typeof x === "number" && !Number.isNaN(x) && x >= TEMP_MIN_C && x <= TEMP_MAX_C,
  );
  if (vals.length === 0) return null;
  return Math.max(...vals);
}

/** brakes_temperature_c °C — reject values outside physical range (bad ingest / wrong field). */
export function brakesTempFromRow(row: TelemetryHistoryRow): number | null {
  const t = row.brakes_temperature_c;
  if (typeof t !== "number" || Number.isNaN(t)) return null;
  if (t < TEMP_MIN_C || t > TEMP_MAX_C) return null;
  return t;
}

export function energyOrFuelValue(
  row: TelemetryHistoryRow,
  electric: boolean,
): number | null {
  if (electric) {
    const e = row.energy_consumption_kwh;
    if (typeof e !== "number" || Number.isNaN(e) || e < 0 || e > ENERGY_MAX_KWH) return null;
    return e;
  }
  const f = row.fuel_level_percent;
  if (typeof f !== "number" || Number.isNaN(f) || f < 0 || f > 100) return null;
  return f;
}

/**
 * Catenary voltage in kV. If value looks like volts (e.g. 25100), convert to kV.
 * Drops non-physical values so they don't blow the Y scale.
 */
export function voltageValue(row: TelemetryHistoryRow): number | null {
  let kv = row.catenary_voltage_kv ?? row.voltage_kv;
  if (typeof kv !== "number" || Number.isNaN(kv)) return null;
  if (kv > 45) kv = kv / 1000;
  if (kv < 0 || kv > VOLTAGE_MAX_KV) return null;
  return kv;
}

export function currentValue(row: TelemetryHistoryRow): number | null {
  const a = row.traction_current_a ?? row.current_a;
  if (typeof a !== "number" || Number.isNaN(a)) return null;
  if (a < 0 || a > CURRENT_MAX_A) return null;
  return a;
}

export function pneumaticValue(row: TelemetryHistoryRow): number | null {
  const p = row.pneumatic_pressure_bar;
  if (typeof p !== "number" || Number.isNaN(p)) return null;
  if (p < 0 || p > PRESSURE_MAX_BAR) return null;
  return p;
}

/** Minutes relative to `nowMs`: 0 = now, negative = past. */
export function rowsToPoints(
  rows: TelemetryHistoryRow[],
  nowMs: number,
  windowMin: number,
  getY: (row: TelemetryHistoryRow) => number | null,
): TrendPoint[] {
  const fromMs = nowMs - windowMin * 60_000;
  const pts: TrendPoint[] = [];
  for (const row of rows) {
    const ts = row.timestamp;
    if (!ts) continue;
    const tMs = new Date(ts).getTime();
    if (tMs < fromMs || tMs > nowMs) continue;
    const y = getY(row);
    if (y == null || Number.isNaN(y)) continue;
    const m = (tMs - nowMs) / 60_000;
    pts.push({ m, v: y });
  }
  pts.sort((a, b) => a.m - b.m);
  return pts;
}

export function lastV(points: TrendPoint[]): number | null {
  if (points.length === 0) return null;
  return points[points.length - 1]!.v;
}
