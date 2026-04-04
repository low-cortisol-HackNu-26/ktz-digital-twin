from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_db
from ...config import settings
from ...core import runtime_state

router = APIRouter(tags=["system"])


def _utcnow() -> str:
	return datetime.now(timezone.utc).isoformat()


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict[str, object]:
	db_ok = True
	redis_ok = True

	try:
		await db.execute(text("SELECT 1"))
	except Exception:
		db_ok = False

	if runtime_state.redis_client is not None:
		try:
			await runtime_state.redis_client.ping()
		except Exception:
			redis_ok = False
	else:
		# Redis might become available after app startup; try one lazy reconnect.
		try:
			runtime_state.redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
			await runtime_state.redis_client.ping()
			redis_ok = True
		except Exception:
			redis_ok = False

	status = "ok" if db_ok else "degraded"
	return {
		"status": status,
		"db": db_ok,
		"redis": redis_ok,
		"timestamp": _utcnow(),
	}


@router.get("/ready")
async def ready(db: AsyncSession = Depends(get_db)) -> dict[str, object]:
	await db.execute(text("SELECT 1"))
	return {"status": "ready", "timestamp": _utcnow()}
