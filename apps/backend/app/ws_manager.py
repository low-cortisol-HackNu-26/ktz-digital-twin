from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class WSManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._clients: set[WebSocket] = set()
        self._subscriptions: dict[WebSocket, str | None] = {}
        self._fleet_watchers: set[WebSocket] = set()
        self._loc_watchers: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, locomotive_id: str | None = None) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)
            self._subscriptions[websocket] = locomotive_id
            if locomotive_id is None:
                self._fleet_watchers.add(websocket)
            else:
                self._loc_watchers[locomotive_id].add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)
            loc = self._subscriptions.pop(websocket, None)
            self._fleet_watchers.discard(websocket)
            if loc is not None and loc in self._loc_watchers:
                self._loc_watchers[loc].discard(websocket)

    async def update_subscription(self, websocket: WebSocket, locomotive_id: str | None) -> None:
        async with self._lock:
            prev = self._subscriptions.get(websocket)
            if prev is not None and prev in self._loc_watchers:
                self._loc_watchers[prev].discard(websocket)
            self._fleet_watchers.discard(websocket)
            self._subscriptions[websocket] = locomotive_id
            if locomotive_id is None:
                self._fleet_watchers.add(websocket)
            else:
                self._loc_watchers[locomotive_id].add(websocket)

    @property
    def clients_count(self) -> int:
        return len(self._clients)

    async def broadcast_telemetry(self, locomotive_id: str, payload: dict[str, Any]) -> None:
        message = json.dumps(
            {"type": "telemetry", "locomotive_id": locomotive_id, "payload": payload},
            default=str,
        )

        async with self._lock:
            targets = set(self._fleet_watchers)
            targets.update(self._loc_watchers.get(locomotive_id, set()))

        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        for ws in dead:
            await self.disconnect(ws)


ws_manager = WSManager()
