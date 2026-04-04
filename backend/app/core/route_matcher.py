"""
Route-snapping engine.

Given a raw GPS point (lat, lng), finds the nearest railway route and returns
the perpendicular snap point on that route's polyline, the distance to it, and
how far along the route the locomotive currently is.

All geometry is done with the Haversine formula (great-circle distances).
Planar projection is used only for the within-segment interpolation step, which
is accurate enough for segments < 300 km long.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# Locomotives must be within this distance of a route to be considered "on" it.
SNAP_THRESHOLD_KM: float = 1.0

_EARTH_R_KM: float = 6_371.0


# ---------------------------------------------------------------------------
# Low-level geometry helpers
# ---------------------------------------------------------------------------

def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two WGS-84 points in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * _EARTH_R_KM * math.asin(math.sqrt(a))


def _closest_on_segment(
    px: float, py: float,
    ax: float, ay: float,
    bx: float, by: float,
) -> tuple[float, float, float]:
    """
    Returns (cx, cy, t) where (cx, cy) is the closest point on segment AB to P,
    and t ∈ [0, 1] is the parametric position along AB.

    Uses planar (Cartesian) projection — fine for segments < 300 km.
    """
    dx, dy = bx - ax, by - ay
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq == 0.0:
        return ax, ay, 0.0
    t = ((px - ax) * dx + (py - ay) * dy) / seg_len_sq
    t = max(0.0, min(1.0, t))
    return ax + t * dx, ay + t * dy, t


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class SnapResult:
    route_id: str
    route_code: str
    route_name: str
    snapped_lat: float
    snapped_lng: float
    distance_km: float
    # Percentage (0–100) of how far along the route the locomotive is
    progress_pct: float


def snap_to_route(
    lat: float,
    lng: float,
    route_id: str,
    route_code: str,
    route_name: str,
    coordinates: list[list[float]],  # [[lng, lat], ...] GeoJSON order
) -> tuple[float, float, float, float] | None:
    """
    Snaps (lat, lng) to the nearest point on the given polyline.

    Returns (snapped_lat, snapped_lng, distance_km, progress_pct)
    or None if the polyline has fewer than 2 points.
    """
    if len(coordinates) < 2:
        return None

    # Pre-compute segment lengths for the progress calculation
    seg_lengths: list[float] = []
    for i in range(len(coordinates) - 1):
        a, b = coordinates[i], coordinates[i + 1]
        seg_lengths.append(_haversine_km(a[1], a[0], b[1], b[0]))
    total_km = sum(seg_lengths)

    best_dist = math.inf
    best_lat = lat
    best_lng = lng
    best_seg = 0
    best_t = 0.0

    for i in range(len(coordinates) - 1):
        a = coordinates[i]      # [lng, lat]
        b = coordinates[i + 1]  # [lng, lat]

        # Note: _closest_on_segment works in (x=lng, y=lat) space
        clng, clat, t = _closest_on_segment(lng, lat, a[0], a[1], b[0], b[1])
        dist = _haversine_km(lat, lng, clat, clng)

        if dist < best_dist:
            best_dist = dist
            best_lat, best_lng = clat, clng
            best_seg = i
            best_t = t

    if total_km > 0:
        dist_along = sum(seg_lengths[:best_seg]) + best_t * seg_lengths[best_seg]
        progress_pct = min(100.0, (dist_along / total_km) * 100.0)
    else:
        progress_pct = 0.0

    return best_lat, best_lng, best_dist, progress_pct


def match_position(
    lat: float,
    lng: float,
    routes: list,  # list[Route] ORM objects
) -> SnapResult | None:
    """
    Finds the nearest route within SNAP_THRESHOLD_KM and returns a SnapResult.
    Returns None if no route is close enough.
    """
    best: SnapResult | None = None
    best_dist = math.inf

    for route in routes:
        result = snap_to_route(
            lat, lng,
            route_id=route.id,
            route_code=route.code,
            route_name=route.name,
            coordinates=route.coordinates,
        )
        if result is None:
            continue

        snapped_lat, snapped_lng, dist_km, progress_pct = result

        if dist_km < best_dist:
            best_dist = dist_km
            best = SnapResult(
                route_id=route.id,
                route_code=route.code,
                route_name=route.name,
                snapped_lat=snapped_lat,
                snapped_lng=snapped_lng,
                distance_km=dist_km,
                progress_pct=progress_pct,
            )

    if best is None or best.distance_km > SNAP_THRESHOLD_KM:
        return None

    return best
