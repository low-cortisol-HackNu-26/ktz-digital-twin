from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class WebSocketManager:
	def __init__(self) -> None:
		self._connections: dict[str, set[WebSocket]] = defaultdict(set)

	@property
	def client_count(self) -> int:
		return sum(len(bucket) for bucket in self._connections.values())

	async def connect(self, locomotive_id: str, websocket: WebSocket) -> None:
		await websocket.accept()
		self._connections[locomotive_id].add(websocket)

	async def disconnect(self, locomotive_id: str, websocket: WebSocket) -> None:
		bucket = self._connections.get(locomotive_id)
		if bucket is None:
			return
		bucket.discard(websocket)
		if not bucket:
			self._connections.pop(locomotive_id, None)

	async def broadcast(self, event: dict[str, Any]) -> None:
		locomotive_id = event.get("locomotive_id")
		if not isinstance(locomotive_id, str):
			return

		bucket = list(self._connections.get(locomotive_id, set()))
		if not bucket:
			return

		message = json.dumps(event, ensure_ascii=True)
		for ws in bucket:
			try:
				await ws.send_text(message)
			except Exception:
				await self.disconnect(locomotive_id, ws)


manager = WebSocketManager()
