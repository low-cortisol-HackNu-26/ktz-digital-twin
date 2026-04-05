import { getDispatcherApiBase, getValidAccessToken } from "@/lib/dispatcherAuth";

export type LocoStatusInfo = {
  locomotive_id: string;
  display_name?: string | null;
  lat: number;
  lng: number;
  speed_kph: number;
  heading?: number | null;
  route_code?: string | null;
  route_name?: string | null;
  progress_pct?: number | null;
  is_online: boolean;
  active_warnings_count: number;
  active_critical_count: number;
  active_noncritical_count: number;
  last_updated: string;
};

export type FleetStatusResponse = {
  locomotives: LocoStatusInfo[];
  total_locomotives: number;
  locomotives_online: number;
  active_warnings_count: number;
};

export type RouteCollection = {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    id: string;
    geometry: { type: "LineString"; coordinates: [number, number][] };
    properties: { id: string; code: string; name: string; total_length_km: number };
  }>;
};

async function authHeaders(): Promise<HeadersInit> {
  const token = await getValidAccessToken();
  if (!token) throw new Error("Не авторизован");
  return { Authorization: `Bearer ${token}` };
}

export async function fetchDispatcherFleet(): Promise<FleetStatusResponse | null> {
  try {
    const h = await authHeaders();
    const res = await fetch(`${getDispatcherApiBase()}/api/dispatcher/fleet`, {
      headers: { ...h },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as FleetStatusResponse;
  } catch {
    return null;
  }
}

export async function fetchDispatcherMapRoutes(): Promise<RouteCollection | null> {
  try {
    const h = await authHeaders();
    const res = await fetch(`${getDispatcherApiBase()}/api/dispatcher/map/routes`, {
      headers: { ...h },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as RouteCollection;
  } catch {
    return null;
  }
}

export type LocoDetailsWarning = {
  warning_id: string;
  rule_id: string;
  severity: string;
  title: string;
  message: string;
  first_seen_at: string;
};

export type LocomotiveDetailsResponse = {
  locomotive_id: string;
  name?: string;
  status?: string;
  current_position?: {
    lat: number | null;
    lng: number | null;
    speed_kph: number;
    route_name?: string | null;
    last_updated?: string | null;
  };
  active_warnings_count?: number;
  warnings?: LocoDetailsWarning[];
  error?: string;
};

export async function fetchLocomotiveDetails(
  locomotiveId: string,
): Promise<LocomotiveDetailsResponse | null> {
  try {
    const h = await authHeaders();
    const res = await fetch(
      `${getDispatcherApiBase()}/api/dispatcher/locomotive/${encodeURIComponent(locomotiveId)}`,
      { headers: { ...h }, cache: "no-store" },
    );
    if (!res.ok) return null;
    return (await res.json()) as LocomotiveDetailsResponse;
  } catch {
    return null;
  }
}

export function lngLatToLeafletPair(coords: [number, number][]): [number, number][] {
  return coords.map(([lng, lat]) => [lat, lng]);
}

/** Sidebar / card subtitle when API omits route_name (uses GeoJSON from map sync). */
export function fleetLocoSubtitle(l: LocoStatusInfo, routes: RouteCollection | null): string {
  if (l.route_name?.trim()) return l.route_name.trim();
  const code = l.route_code?.trim();
  if (code) {
    const hit = routes?.features?.find(
      (f) => f.properties?.code?.toUpperCase() === code.toUpperCase(),
    );
    if (hit?.properties?.name?.trim()) return hit.properties.name.trim();
    return code;
  }
  const dn = l.display_name?.trim();
  if (dn && dn !== l.locomotive_id) return dn;
  return "Маршрут не привязан";
}

/** PDF from dispatcher: GET …/locomotives/{id}/report/15min */
export async function download15MinReportPdf(
  locomotiveId: string,
): Promise<{ ok: true } | { ok: false; message: string }> {
  try {
    const h = await authHeaders();
    const url = `${getDispatcherApiBase()}/api/dispatcher/locomotives/${encodeURIComponent(locomotiveId)}/report/15min`;
    const res = await fetch(url, { headers: { ...h } });
    if (!res.ok) {
      let msg = `Ошибка ${res.status}`;
      try {
        const j = (await res.json()) as { detail?: string; error?: string };
        msg = j.detail || j.error || msg;
      } catch {
        /* ignore */
      }
      return { ok: false, message: msg };
    }
    const blob = await res.blob();
    const cd = res.headers.get("Content-Disposition");
    const match = cd?.match(/filename="?([^";]+)"?/i);
    const filename = match?.[1] ?? `${locomotiveId}_15min_report.pdf`;
    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = filename;
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(objectUrl);
    return { ok: true };
  } catch (e) {
    return { ok: false, message: e instanceof Error ? e.message : "Сбой загрузки" };
  }
}
