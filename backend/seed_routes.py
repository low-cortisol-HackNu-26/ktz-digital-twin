"""
One-shot script: creates the database (if needed), tables, and inserts KZ railway routes.

Usage (from backend/ with the venv active):
    python seed_routes.py

Reads DATABASE_URL from .env — same source as the FastAPI app.
Idempotent: routes with duplicate codes are skipped.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import asyncpg
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.session import Base
from app.models import AuthSession, DriverAccount, LocomotivePosition, Route  # noqa: F401

# Load from simulator-fetched JSON if available, otherwise use hardcoded fallback
_ROUTES_FILE = Path(__file__).parent.parent / "simulator" / "data" / "ktz_routes.json"

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

if _ROUTES_FILE.exists():
    import json as _json
    ROUTES: list[dict] = _json.loads(_ROUTES_FILE.read_text())
    print(f"  loaded {len(ROUTES)} routes from {_ROUTES_FILE}")
else:
    ROUTES = _FALLBACK_ROUTES
    print(f"  using {len(ROUTES)} hardcoded fallback routes (run simulator/fetch_routes.py for real OSM data)")


def _parse_url() -> dict:
    """Extract connection params from DATABASE_URL for raw asyncpg use."""
    from sqlalchemy.engine import make_url
    u = make_url(settings.DATABASE_URL)
    return {
        "host": u.host or "127.0.0.1",
        "port": u.port or 5432,
        "user": u.username or "postgres",
        "password": u.password or "",
        "database": u.database or "locomotive_twin",
    }


async def _ensure_database(params: dict) -> None:
    """Connect to the postgres maintenance DB and create the target DB if missing."""
    conn = await asyncpg.connect(
        host=params["host"],
        port=params["port"],
        user=params["user"],
        password=params["password"],
        database="postgres",  # always exists
    )
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", params["database"]
        )
        if not exists:
            # CREATE DATABASE cannot run inside a transaction
            await conn.execute(f'CREATE DATABASE "{params["database"]}"')
            print(f"  created database '{params['database']}'")
        else:
            print(f"  database '{params['database']}' already exists")
    finally:
        await conn.close()


async def _ensure_tables(engine) -> None:
    """Run SQLAlchemy create_all to create any missing tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("  tables ready")


async def seed() -> None:
    params = _parse_url()

    print(f"\n[1/3] Ensuring database '{params['database']}' exists...")
    await _ensure_database(params)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    print("\n[2/3] Ensuring tables exist...")
    await _ensure_tables(engine)

    print("\n[3/3] Seeding routes...")
    async with session_factory() as session:
        inserted = skipped = 0
        for r in ROUTES:
            existing = (
                await session.execute(select(Route).where(Route.code == r["code"]))
            ).scalar_one_or_none()
            if existing is not None:
                print(f"  skip  {r['code']} — already exists")
                skipped += 1
                continue
            session.add(Route(
                code=r["code"],
                name=r["name"],
                coordinates=r["coordinates"],
                total_length_km=r["total_length_km"],
            ))
            print(f"  added {r['code']} ({r['name']})")
            inserted += 1
        await session.commit()

    await engine.dispose()
    print(f"\nDone — {inserted} inserted, {skipped} skipped.")


if __name__ == "__main__":
    asyncio.run(seed())
