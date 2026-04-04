from __future__ import annotations

import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.deps import get_db
from ..models.telemetry import CurrentSnapshot
from .manager import manager

router = APIRouter(tags=["ws"])


@router.websocket("/ws/telemetry/{locomotive_id}")
async def telemetry_ws(
	websocket: WebSocket,
	locomotive_id: str,
	db: AsyncSession = Depends(get_db),
) -> None:
	await manager.connect(locomotive_id, websocket)
	try:
		latest = (
			await db.execute(
				select(CurrentSnapshot).where(CurrentSnapshot.locomotive_id == locomotive_id)
			)
		).scalar_one_or_none()
		if latest is not None:
			await websocket.send_text(json.dumps(latest.payload, ensure_ascii=True))

		while True:
			message = await websocket.receive_text()
			if message.strip().lower() == "ping":
				await websocket.send_text("pong")
	except WebSocketDisconnect:
		pass
	finally:
		await manager.disconnect(locomotive_id, websocket)
