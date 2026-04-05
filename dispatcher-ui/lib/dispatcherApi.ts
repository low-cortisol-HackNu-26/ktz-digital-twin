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
