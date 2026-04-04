# WebSocket connection manager — fan-out to all connected clients for a locomotive.
#
# class WebSocketManager:
#   _connections: dict[str, set[WebSocket]]
#     key = locomotiveId; value = set of active WebSocket connections
#
#   async connect(locomotiveId: str, ws: WebSocket) -> None
#     Accept ws, add to _connections[locomotiveId]
#     Enforce WS_MAX_CLIENTS_PER_LOCO limit; close oldest if exceeded
#
#   async disconnect(locomotiveId: str, ws: WebSocket) -> None
#     Remove from set; clean up empty key
#
#   async broadcast(locomotiveId: str, data: dict) -> None
#     JSON-encode data, send_text to all connections for that locomotive
#     Remove disconnected clients (handle WebSocketDisconnect silently)
#
#   async broadcast_all(data: dict) -> None
#     Broadcast to every connected client (used for system-wide alerts)
#
# The manager subscribes to Redis pub/sub channel "telemetry:{locomotiveId}"
# and calls broadcast() on each received message.
# This decouples ingestion from fan-out and supports multiple backend workers.
