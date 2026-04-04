# Service health and threshold configuration routes.
#
# GET /health
#   No auth required — used by Docker healthcheck and load balancer
#   Returns: { status: "ok", db: bool, redis: bool, timestamp: str }
#   Checks DB with SELECT 1 and Redis with PING
#
# GET /api/thresholds
#   Auth: any authenticated user
#   Returns current ThresholdsConfig loaded from thresholds.json
#
# PUT /api/thresholds
#   Auth: Admin role only
#   Body: ThresholdsConfig
#   Validates, saves to thresholds.json (or DB), reloads in-memory singleton
#   Returns updated config
