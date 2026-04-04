"""
Inserts KTZ railway routes into the DB at startup if the routes table is empty.

Route data is loaded from simulator/data/ktz_routes.json when available
(populated by `python simulator/fetch_routes.py`), otherwise falls back
to hardcoded coordinates.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.route import Route

logger = logging.getLogger(__name__)

# Path is relative to this file: backend/app/core/ → up 3 dirs → repo root
_ROUTES_FILE = Path(__file__).parent.parent.parent.parent / "simulator" / "data" / "ktz_routes.json"

_FALLBACK_ROUTES: list[dict] = [
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


def _load_routes() -> list[dict]:
    if _ROUTES_FILE.exists():
        try:
            routes = json.loads(_ROUTES_FILE.read_text())
            logger.info("route_seeder: loaded %d routes from %s", len(routes), _ROUTES_FILE)
            return routes
        except Exception as exc:
            logger.warning("route_seeder: failed to read %s: %s — using fallback", _ROUTES_FILE, exc)
    return _FALLBACK_ROUTES


async def seed_routes_if_empty(session: AsyncSession) -> None:
    """Insert all routes if the table is empty. Safe to call on every startup."""
    count = (await session.execute(select(Route))).scalars().first()
    if count is not None:
        logger.info("route_seeder: routes already present, skipping seed")
        return

    routes = _load_routes()
    for r in routes:
        session.add(Route(
            code=r["code"],
            name=r["name"],
            coordinates=r["coordinates"],
            total_length_km=float(r.get("total_length_km", 0.0)),
        ))
    await session.commit()
    logger.info("route_seeder: inserted %d routes", len(routes))
