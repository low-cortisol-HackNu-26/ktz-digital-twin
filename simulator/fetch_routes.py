"""
Fetches real KTZ railway routes from OpenStreetMap via Overpass API.

Saves to  simulator/data/ktz_routes.json  which is read by both:
  - the simulator (locomotive GPS movement)
  - backend/seed_routes.py  (DB seeder)

Run once before starting the system:
    cd simulator
    python fetch_routes.py

Requirements: httpx  (already in simulator/requirements.txt)
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Overpass query
# ---------------------------------------------------------------------------
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Kazakhstan bounding box: south=40.5 west=49.0 north=55.5 east=88.0
QUERY = """
[out:json][timeout:120];
(
  relation["type"="route"]["route"="train"](40.5,49.0,55.5,88.0);
);
out geom;
"""

# ---------------------------------------------------------------------------
# Name patterns → (code, display_name) for the routes we care about
# ---------------------------------------------------------------------------
ROUTE_PATTERNS: list[tuple[list[str], str, str]] = [
    (["алматы", "astana", "нур-султ", "nur-sultan", "астана"],   "ALA-NUR", "Almaty — Nur-Sultan"),
    (["алматы", "шымкент", "shymkent", "чимкент"],               "ALA-SHY", "Almaty — Shymkent"),
    (["нур-султ", "astana", "астана", "петропавл", "petropavl"],  "NUR-PET", "Nur-Sultan — Petropavl"),
    (["нур-султ", "astana", "астана", "актобе", "aktobe"],        "NUR-AKT", "Nur-Sultan — Aktobe"),
    (["шымкент", "shymkent", "қызылорда", "kyzylorda", "кызылорда"], "SHY-KYZ", "Shymkent — Kyzylorda"),
]

# ---------------------------------------------------------------------------
# Approximate total lengths (km) for each route
# ---------------------------------------------------------------------------
ROUTE_LENGTHS: dict[str, float] = {
    "ALA-NUR": 1295.0,
    "ALA-SHY": 705.0,
    "NUR-PET": 280.0,
    "NUR-AKT": 1090.0,
    "SHY-KYZ": 605.0,
}

# ---------------------------------------------------------------------------
# Fallback hardcoded routes (used when Overpass is unavailable)
# ---------------------------------------------------------------------------
FALLBACK_ROUTES: list[dict] = [
    {
        "code": "ALA-NUR",
        "name": "Almaty — Nur-Sultan",
        "total_length_km": 1295.0,
        "coordinates": [
            [76.9286, 43.2567], [77.0500, 43.8500], [77.1200, 44.4000],
            [77.0000, 44.8500], [76.1500, 45.5000], [75.3000, 46.2000],
            [74.9950, 46.8474], [74.0000, 47.8000], [73.6000, 48.6000],
            [73.0884, 49.8073], [72.5000, 50.4000], [71.9500, 50.8500],
            [71.4460, 51.1801],
        ],
    },
    {
        "code": "ALA-SHY",
        "name": "Almaty — Shymkent",
        "total_length_km": 705.0,
        "coordinates": [
            [76.9286, 43.2567], [76.0000, 43.0000], [74.5000, 42.8500],
            [73.0000, 42.7000], [71.9000, 42.6000], [71.3713, 42.3167],
            [70.8000, 42.2000], [69.5900, 42.3170],
        ],
    },
    {
        "code": "NUR-AKT",
        "name": "Nur-Sultan — Aktobe",
        "total_length_km": 1090.0,
        "coordinates": [
            [71.4460, 51.1801], [70.0000, 51.5000], [68.0000, 52.0000],
            [66.0000, 52.5000], [64.5000, 52.8000], [63.6240, 53.2143],
            [62.0000, 52.5000], [60.0000, 51.5000], [57.1530, 50.3001],
        ],
    },
    {
        "code": "NUR-PET",
        "name": "Nur-Sultan — Petropavl",
        "total_length_km": 280.0,
        "coordinates": [
            [71.4460, 51.1801], [71.5000, 51.8000], [71.6000, 52.4000],
            [71.7000, 52.9000], [71.9522, 54.8650],
        ],
    },
    {
        "code": "SHY-KYZ",
        "name": "Shymkent — Kyzylorda",
        "total_length_km": 605.0,
        "coordinates": [
            [69.5900, 42.3170], [68.5000, 43.0000], [67.5000, 43.8000],
            [66.8000, 44.3000], [65.5500, 44.8530],
        ],
    },
]


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _haversine_km(p1: list[float], p2: list[float]) -> float:
    """Distance in km between two [lng, lat] points."""
    lon1, lat1 = math.radians(p1[0]), math.radians(p1[1])
    lon2, lat2 = math.radians(p2[0]), math.radians(p2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def _route_length_km(coords: list[list[float]]) -> float:
    total = 0.0
    for i in range(len(coords) - 1):
        total += _haversine_km(coords[i], coords[i + 1])
    return total


# ---------------------------------------------------------------------------
# Way stitching
# ---------------------------------------------------------------------------

def _node_key(lat: float, lon: float) -> tuple:
    """Round to ~11m precision for matching endpoints."""
    return (round(lat, 4), round(lon, 4))


def _stitch_ways(ways: list[list[list[float]]]) -> list[list[float]]:
    """
    Stitch a list of ways (each: [[lng, lat], ...]) into a single ordered polyline.
    Uses greedy endpoint matching; handles gaps by nearest-neighbor jump.
    Returns [[lng, lat], ...].
    """
    if not ways:
        return []
    if len(ways) == 1:
        return ways[0]

    # Convert each way to a mutable segment with first/last endpoint keys
    segments: list[list[list[float]]] = [list(w) for w in ways]

    result = segments.pop(0)

    while segments:
        tail = result[-1]
        head = result[0]

        best_idx = -1
        best_dist = float("inf")
        best_prepend = False
        best_reverse = False

        for i, seg in enumerate(segments):
            seg_head = seg[0]
            seg_tail = seg[-1]

            # Candidate connections: tail→seg_head, tail→seg_tail(reversed),
            #                        seg_tail→head, seg_head(reversed)→head
            for dist, prepend, reverse in [
                (_haversine_km(tail, seg_head), False, False),
                (_haversine_km(tail, seg_tail), False, True),
                (_haversine_km(seg_tail, head), True, False),
                (_haversine_km(seg_head, head), True, True),
            ]:
                if dist < best_dist:
                    best_dist = dist
                    best_idx = i
                    best_prepend = prepend
                    best_reverse = reverse

        seg = segments.pop(best_idx)
        if best_reverse:
            seg = seg[::-1]

        if best_prepend:
            result = seg + result
        else:
            result = result + seg

    return result


# ---------------------------------------------------------------------------
# Classify a relation by name into one of our route codes
# ---------------------------------------------------------------------------

def _classify_relation(tags: dict) -> tuple[str, str] | None:
    """Return (code, name) if this relation matches a known KTZ route."""
    name_raw = (
        tags.get("name", "") + " " +
        tags.get("name:en", "") + " " +
        tags.get("name:ru", "") + " " +
        tags.get("ref", "")
    ).lower()

    for keywords, code, display_name in ROUTE_PATTERNS:
        # All keywords must appear in the name
        if all(kw in name_raw for kw in keywords):
            return code, display_name

    return None


# ---------------------------------------------------------------------------
# Parse Overpass response
# ---------------------------------------------------------------------------

def _parse_relations(data: dict) -> list[dict]:
    """
    Extract route geometries from Overpass JSON response.
    Returns list of {code, name, total_length_km, coordinates} dicts.
    """
    found: dict[str, dict] = {}

    for element in data.get("elements", []):
        if element.get("type") != "relation":
            continue

        tags = element.get("tags", {})
        match = _classify_relation(tags)
        if match is None:
            continue

        code, display_name = match
        if code in found:
            continue  # already have this route

        # Collect way geometries
        ways: list[list[list[float]]] = []
        for member in element.get("members", []):
            if member.get("type") != "way":
                continue
            geom = member.get("geometry", [])
            if not geom:
                continue
            # Convert {lat, lon} → [lng, lat] (our format)
            way_pts = [[pt["lon"], pt["lat"]] for pt in geom]
            ways.append(way_pts)

        if not ways:
            continue

        coords = _stitch_ways(ways)
        if len(coords) < 2:
            continue

        # Simplify: keep every Nth point to stay under ~500 waypoints
        n = max(1, len(coords) // 300)
        simplified = coords[::n]
        if simplified[-1] != coords[-1]:
            simplified.append(coords[-1])

        length_km = _route_length_km(simplified)

        found[code] = {
            "code": code,
            "name": display_name,
            "total_length_km": round(length_km, 1),
            "coordinates": simplified,
        }
        print(f"  found {code} ({display_name}): {len(simplified)} waypoints, {length_km:.0f} km")

    return list(found.values())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def fetch() -> list[dict]:
    print("Querying Overpass API for KTZ railway routes...")
    try:
        response = httpx.post(
            OVERPASS_URL,
            data={"data": QUERY},
            headers={"User-Agent": "KTZ-Digital-Twin-Hackathon/1.0"},
            timeout=130.0,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        print(f"  Overpass unavailable: {exc}")
        print("  Using fallback hardcoded routes.")
        return FALLBACK_ROUTES

    routes = _parse_relations(data)

    # Fill in any routes that Overpass didn't return
    found_codes = {r["code"] for r in routes}
    for fallback in FALLBACK_ROUTES:
        if fallback["code"] not in found_codes:
            print(f"  {fallback['code']} not found in Overpass — using fallback")
            routes.append(fallback)

    return routes


def main() -> None:
    routes = fetch()

    out_path = Path(__file__).parent / "data" / "ktz_routes.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(routes, ensure_ascii=False, indent=2))
    print(f"\nSaved {len(routes)} routes → {out_path}")
    print("\nRoute summary:")
    for r in routes:
        print(f"  {r['code']:10s}  {r['total_length_km']:6.0f} km  {len(r['coordinates'])} waypoints")

    print("\nDone. You can now start the simulator and backend.")


if __name__ == "__main__":
    main()
