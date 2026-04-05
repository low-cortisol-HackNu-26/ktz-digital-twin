/**
 * Telemetry REST — no auth on GET /api/locomotives/{id}/current (ingest pipeline).
 */

import { getApiBase } from "@/lib/authClient";

/** Default locomotive for simulator + dashboard when env is unset. */
export const DEFAULT_TELEMETRY_LOCOMOTIVE_ID = "KZ8A-0001";

/** Fields from GET /api/locomotives/{id}/current `event` (simulator JSON). */
export type TelemetryEventCurrent = {
  timestamp: string;
  locomotive_id: string;
  speed_kph: number;
  target_speed_kph?: number;
  allowed_speed_kph?: number;
  acceleration?: number;
  traction_mode?: string;
  tractive_effort_kn?: number;
  brake_pipe_pressure_bar?: number;
  brake_cylinder_pressure_bar?: number;
  pantograph_up?: boolean;
  catenary_voltage_kv?: number;
  traction_current_a?: number;
  traction_power_kw?: number;
  traction_type?:string;
  regen_power_kw?: number;
  transformer_temp_c?: number;
  energy_consumption_kwh?:number;
  converter_temp_c?: number;
  traction_motor_temp_c?: number;
  axle_bearing_temp_c?: number;
  compressor_state?: string;
  pneumatic_pressure_bar?: number;
  vibration_motor?: number;
  vibration_gearbox?: number;
  gps_lat: number | null;
  gps_lon: number | null;
  route_segment: string | null;
  gradient_permille?: number;
  train_mass_tons?: number;
  active_fault_codes?: string[];
  signal_quality?: number;
  data_quality?: number;
  ingestion_time?: string;
  source?: string;
  schema_version?: string;
};

export type ActiveWarningCurrent = {
  warning_id: string;
  locomotive_id: string;
  rule_id: string;
  severity: string;
  title: string;
  message: string;
  recommended_action: string;
  active: boolean;
  first_seen_at: string;
  last_seen_at: string;
};

export type LocomotiveCurrentResponse = {
  locomotive_id: string;
  event: TelemetryEventCurrent | null;
  active_warnings: ActiveWarningCurrent[];
};

function normalizeCurrentPayload(raw: unknown): LocomotiveCurrentResponse | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const locomotive_id = typeof o.locomotive_id === "string" ? o.locomotive_id : "";
  const active_warnings = Array.isArray(o.active_warnings) ? o.active_warnings : [];
  return {
    locomotive_id,
    event: (o.event ?? null) as TelemetryEventCurrent | null,
    active_warnings: active_warnings as ActiveWarningCurrent[],
  };
}

export async function fetchLocomotiveCurrent(
  locomotiveId: string,
): Promise<LocomotiveCurrentResponse | null> {
  if (!locomotiveId) return null;
  try {
    const res = await fetch(
      `${getApiBase()}/api/locomotives/${encodeURIComponent(locomotiveId)}/current`,
      { cache: "no-store" },
    );
    if (!res.ok) return null;
    return normalizeCurrentPayload(await res.json());
  } catch {
    return null;
  }
}

/** Active warnings from GET /api/locomotives/{id}/warnings */
export async function fetchLocomotiveWarnings(locomotiveId: string): Promise<ActiveWarningCurrent[]> {
  if (!locomotiveId) return [];
  try {
    const res = await fetch(
      `${getApiBase()}/api/locomotives/${encodeURIComponent(locomotiveId)}/warnings`,
      { cache: "no-store" },
    );
    if (!res.ok) return [];
    const raw = await res.json();
    return Array.isArray(raw) ? (raw as ActiveWarningCurrent[]) : [];
  } catch {
    return [];
  }
}

/** Warnings shown on the Alerts tab: `current.active_warnings` (same rules as latest snapshot). */
export async function fetchActiveWarningsViaCurrent(
  locomotiveId: string,
): Promise<ActiveWarningCurrent[]> {
  const current = await fetchLocomotiveCurrent(locomotiveId);
  return current?.active_warnings ?? [];
}

/** e.g. "ALA-NUR:002" → "ALA-NUR" */
export function routeCodeFromSegment(routeSegment: string | null | undefined): string | null {
  if (!routeSegment?.trim()) return null;
  const code = routeSegment.split(":")[0]?.trim();
  return code || null;
}
