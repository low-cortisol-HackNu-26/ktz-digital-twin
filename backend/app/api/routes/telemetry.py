# REST routes for telemetry ingestion (non-WS path, e.g. batch HTTP POST).
#
# POST /api/telemetry/ingest
#   Body: TelemetryPacketSchema (or list of packets for batch)
#   Auth: require_role("Simulator", "Admin")
#   Steps:
#     1. Validate + smooth via EMA (core/smoothing.py)
#     2. Compute health index (core/health_index.py)
#     3. Persist to DB (models/telemetry.py)
#     4. Publish to Redis pub/sub channel "telemetry:{locomotiveId}"
#     5. Return 202 Accepted
#
# GET /api/telemetry/latest/{locomotiveId}
#   Auth: any authenticated user
#   Returns: latest TelemetryPacket + HealthIndex from DB or Redis cache
#
# GET /api/locomotivies
#   Returns list of known locomotive IDs and display names
