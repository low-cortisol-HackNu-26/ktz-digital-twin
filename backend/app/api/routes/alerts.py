# REST routes for alert management.
#
# GET /api/alerts/active/{locomotiveId}
#   Returns: list of currently active (unacknowledged) alerts
#
# POST /api/alerts/{alertId}/acknowledge
#   Auth: Machinist or Dispatcher role
#   Updates alert.acknowledgedAt in DB
#   Publishes acknowledgement event to Redis (so WS clients update)
#
# GET /api/alerts/history
#   Query params: locomotiveId, from, to, severity (optional filter)
#   Returns: paginated alert history
