/**
 * Single source for health-panel severity and trends reference lines.
 * Keep in sync with operational rules used on the health dashboard.
 */

/** Electric: |energy_consumption_kwh| — high is worse (see electricitySeverity). */
export const ENERGY_ABS_WARN = 7;
export const ENERGY_ABS_CRIT = 9;

/** Diesel/fuel: fuel_level_percent — low is worse (see fuelSeverity). */
export const FUEL_PCT_CRIT_BELOW = 40;
export const FUEL_PCT_WARN_BELOW = 70;

/** Drive / traction temps °C — high is worse. */
export const DRIVE_TEMP_WARN_C = 95;
export const DRIVE_TEMP_CRIT_C = 110;

/** brakes_temperature_c °C — high is worse (brakePipeSeverity in health UI). */
export const BRAKES_TEMP_WARN_C = 140;
export const BRAKES_TEMP_CRIT_C = 180;

/** pneumatic_pressure_bar — low is worse. */
export const PNEUMATIC_WARN_BAR = 6;
export const PNEUMATIC_CRIT_BAR = 5;

/** Catenary / line voltage kV — low is worse. */
export const VOLTAGE_WARN_KV = 20;
export const VOLTAGE_CRIT_KV = 17;

/** Traction current A — high is worse. */
export const CURRENT_WARN_A = 150;
export const CURRENT_CRIT_A = 300;

/** Recharts ReferenceLine entries: amber = warning edge, red = critical edge. */
export type TrendThresholdLine = { y: number; stroke: string; strokeDasharray?: string };

const AMBER = "#f59e0b";
const RED = "#ef4444";

/** Value going above y crosses into worse band (temp, current, energy magnitude, brakes temp). */
export function thresholdsHighIsWorse(warnY: number, critY: number): TrendThresholdLine[] {
  return [
    { y: warnY, stroke: AMBER, strokeDasharray: "5 5" },
    { y: critY, stroke: RED, strokeDasharray: "5 5" },
  ];
}

/** Value going below y crosses into worse band (pneumatic, voltage). */
export function thresholdsLowIsWorse(warnY: number, critY: number): TrendThresholdLine[] {
  return [
    { y: warnY, stroke: AMBER, strokeDasharray: "5 5" },
    { y: critY, stroke: RED, strokeDasharray: "5 5" },
  ];
}

/**
 * Fuel %: above FUEL_PCT_WARN_BELOW is normal; 40–70 warning; below 40 critical.
 * Lines at 70 (enter warning below) and 40 (enter critical below).
 */
export function thresholdsFuelPercent(): TrendThresholdLine[] {
  return [
    { y: FUEL_PCT_WARN_BELOW, stroke: AMBER, strokeDasharray: "5 5" },
    { y: FUEL_PCT_CRIT_BELOW, stroke: RED, strokeDasharray: "5 5" },
  ];
}

/** |kWh| or proxy: above warn/crit absolute is worse. */
export function thresholdsEnergyAbs(): TrendThresholdLine[] {
  return thresholdsHighIsWorse(ENERGY_ABS_WARN, ENERGY_ABS_CRIT);
}

export type YDomainTrendOptions = {
  padRatio?: number;
  /** Ignore data outside this band when computing min/max (outliers / wrong units). Thresholds always included. */
  dataBounds?: { min: number; max: number };
};

/**
 * Y-axis domain that always includes every threshold line and sane data points,
 * so ReferenceLines stay visible without one bogus sample blowing the scale.
 */
export function yDomainForTrends(
  dataValues: number[],
  thresholdLines: { y: number }[],
  options?: YDomainTrendOptions,
): [number, number] {
  const padRatio = options?.padRatio ?? 0.07;
  const bounds = options?.dataBounds;

  const thYs = thresholdLines
    .map((l) => l.y)
    .filter((y) => typeof y === "number" && Number.isFinite(y));
  let dvs = dataValues.filter((v) => typeof v === "number" && Number.isFinite(v));
  if (bounds) {
    dvs = dvs.filter((v) => v >= bounds.min && v <= bounds.max);
  }

  const candidates: number[] = [...dvs, ...thYs];
  if (candidates.length === 0) return [0, 1];

  const rawLo = Math.min(...candidates);
  const rawHi = Math.max(...candidates);
  if (rawLo === rawHi) {
    const pad = Math.max(Math.abs(rawLo) * padRatio, 1e-3);
    const lo = rawLo >= 0 ? Math.max(0, rawLo - pad) : rawLo - pad;
    const hi = rawHi + pad;
    if (!Number.isFinite(lo) || !Number.isFinite(hi) || hi <= lo) return [0, 1];
    return [lo, hi];
  }

  const span = rawHi - rawLo;
  const pad = Math.max(span * padRatio, span * 0.02, 1e-6);
  let lo = rawLo - pad;
  let hi = rawHi + pad;
  if (rawLo >= 0 && lo < 0) lo = 0;
  if (!Number.isFinite(lo) || !Number.isFinite(hi) || hi <= lo) return [0, 1];
  return [lo, hi];
}
