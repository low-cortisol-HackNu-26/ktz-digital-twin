/** Main telemetry API (port 8000) — GET /current is unauthenticated for ingest/demo. */

export type TelemetryEventCurrent = {
  timestamp: string;
  speed_kph: number;
  traction_type?: string;
  fuel_level_percent?: number | null;
  energy_consumption_kwh?: number | null;
  engine_temperature_c?: number | null;
  traction_motor_temp_c?: number | null;
  traction_power_kw?: number | null;
  catenary_voltage_kv?: number | null;
  traction_current_a?: number | null;
  current_a?: number | null;
  route_segment?: string | null;
  route_progress_percent?: number | null;
  distance_to_destination_km?: number | null;
  eta_timestamp?: string | null;
  pneumatic_pressure_bar?: number | null;
};

export type ActiveWarningCurrent = {
  warning_id: string;
  severity: string;
  title: string;
  message: string;
};

export type HealthIndexCurrent = {
  overall_health_index: number;
  timestamp?: string | null;
};

export type LocomotiveCurrentResponse = {
  locomotive_id: string;
  event: TelemetryEventCurrent | null;
  active_warnings: ActiveWarningCurrent[];
  health_index?: HealthIndexCurrent | null;
};

export function getBackendTelemetryBase(): string {
  return (process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000").replace(/\/$/, "");
}

export async function fetchBackendCurrent(
  locomotiveId: string,
): Promise<LocomotiveCurrentResponse | null> {
  if (!locomotiveId) return null;
  try {
    const res = await fetch(
      `${getBackendTelemetryBase()}/api/locomotives/${encodeURIComponent(locomotiveId)}/current`,
      { cache: "no-store" },
    );
    if (!res.ok) return null;
    return (await res.json()) as LocomotiveCurrentResponse;
  } catch {
    return null;
  }
}
