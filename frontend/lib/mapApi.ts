/**
 * Client for existing FastAPI map routes (no backend changes).
 * GET /api/map/routes — FeatureCollection of LineStrings [[lng, lat], ...]
 * GET /api/map/fleet/{locomotive_id} — snapped position + speed
 */

import { getApiBase, getValidAccessToken } from "@/lib/authClient";

export type RouteFeature = {
  type: "Feature";
  id: string;
  geometry: {
    type: "LineString";
    coordinates: [number, number][];
  };
  properties: {
    id: string;
    code: string;
    name: string;
    total_length_km: number;
  };
};

export type RouteCollection = {
  type: "FeatureCollection";
  features: RouteFeature[];
};

export type LocomotivePositionOut = {
  locomotive_id: string;
  lat: number;
  lng: number;
  speed: number;
  heading: number | null;
  route_id: string | null;
  route_code: string | null;
  route_name: string | null;
  snapped_lat: number | null;
  snapped_lng: number | null;
  distance_to_route_m: number | null;
  progress_pct: number | null;
  updated_at: string;
};

/** Leaflet wants [lat, lng]; API GeoJSON uses [lng, lat]. */
export function lngLatToLeafletPair(coords: [number, number][]): [number, number][] {
  return coords.map(([lng, lat]) => [lat, lng]);
}

export async function fetchMapRoutes(): Promise<RouteCollection | null> {
  const token = await getValidAccessToken();
  if (!token) return null;
  const res = await fetch(`${getApiBase()}/api/map/routes`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return null;
  return (await res.json()) as RouteCollection;
}

export async function fetchFleetPosition(
  locomotiveId: string,
): Promise<LocomotivePositionOut | null> {
  const token = await getValidAccessToken();
  if (!token) return null;
  const res = await fetch(
    `${getApiBase()}/api/map/fleet/${encodeURIComponent(locomotiveId)}`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  if (!res.ok) return null;
  return (await res.json()) as LocomotivePositionOut;
}

export function markerFromPosition(p: LocomotivePositionOut): [number, number] {
  if (p.snapped_lat != null && p.snapped_lng != null) {
    return [p.snapped_lat, p.snapped_lng];
  }
  return [p.lat, p.lng];
}

export function pickRoutePolyline(
  routes: RouteCollection,
  routeId: string | null,
): [number, number][] | null {
  if (!routes.features?.length) return null;
  if (routeId) {
    const f = routes.features.find((x) => x.properties.id === routeId);
    if (f?.geometry?.coordinates?.length) {
      return lngLatToLeafletPair(f.geometry.coordinates);
    }
  }
  const first = routes.features[0];
  if (first?.geometry?.coordinates?.length) {
    return lngLatToLeafletPair(first.geometry.coordinates);
  }
  return null;
}

/** Match telemetry `route_segment` prefix (e.g. ALA-NUR) to `properties.code`. */
export function pickRoutePolylineByCode(
  routes: RouteCollection,
  routeCode: string | null,
): [number, number][] | null {
  if (!routes.features?.length || !routeCode) return null;
  const f = routes.features.find(
    (x) => x.properties.code?.toUpperCase() === routeCode.toUpperCase(),
  );
  if (f?.geometry?.coordinates?.length) {
    return lngLatToLeafletPair(f.geometry.coordinates);
  }
  return pickRoutePolyline(routes, null);
}

/** Human route title from GET /api/map/routes (matches telemetry `route_segment` code). */
export function routeDisplayNameFromCollection(
  routes: RouteCollection | null,
  routeCode: string | null,
): string | null {
  if (!routes?.features?.length || !routeCode) return null;
  const f = routes.features.find(
    (x) => x.properties.code?.toUpperCase() === routeCode.toUpperCase(),
  );
  const name = f?.properties?.name?.trim();
  return name || null;
}
