# WebSocket route handler — registered in main.py.
#
# @router.websocket("/ws/telemetry/{locomotiveId}")
# async def telemetry_ws(locomotiveId: str, ws: WebSocket, token: str = Query(...))
#
# Flow:
#   1. Verify JWT from token query param (auth/jwt.py); close with 4001 if invalid
#   2. manager.connect(locomotiveId, ws)
#   3. Send initial "hello" message with latest telemetry from DB/Redis cache
#   4. Enter receive loop:
#      - Receive text (ping/pong heartbeat from client)
#      - Respond to ping with pong to keep connection alive
#      - On disconnect: break loop
#   5. Finally: manager.disconnect(locomotiveId, ws)
#
# Note: data is pushed to clients by manager.broadcast() from Redis listener,
#       not from this receive loop.
#
# @router.websocket("/ws/ingest/{locomotiveId}")
# async def ingest_ws(locomotiveId: str, ws: WebSocket, token: str = Query(...))
#   Receives telemetry packets from the simulator.
#   Validates, smooths, computes health index, persists, publishes to Redis.
