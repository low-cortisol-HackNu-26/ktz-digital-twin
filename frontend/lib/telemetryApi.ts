/**
 * Telemetry REST — no auth on GET /api/locomotives/{id}/current (ingest pipeline).
 */

import { getApiBase } from "@/lib/authClient";

/** Subset of TelemetryEvent fields used by the map. */
export type TelemetryEventCurrent = {
  timestamp: string;
  locomotive_id: string;
  speed_kph: number;
  gps_lat: number | null;
  gps_lon: number | null;
  route_segment: string | null;
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
    return (await res.json()) as LocomotiveCurrentResponse;
  } catch {
    return null;
  }
}

/** e.g. "ALA-NUR:002" → "ALA-NUR" */
export function routeCodeFromSegment(routeSegment: string | null | undefined): string | null {
  if (!routeSegment?.trim()) return null;
  const code = routeSegment.split(":")[0]?.trim();
  return code || null;
}
