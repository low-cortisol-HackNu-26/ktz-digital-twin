# REST routes for historical telemetry data.
#
# GET /api/history
#   Query params: locomotiveId, from (ISO or Unix ms), to, parameters (optional filter list)
#   Auth: any authenticated user
#   Returns: list of TelemetryPacketSchema ordered by timestamp asc
#   Limit: max 10,000 rows; returns 400 if range too large
#   Uses TimescaleDB time_bucket for downsampling if range > 1h (returns 1-min averages)
#
# GET /api/history/events
#   Query params: locomotiveId, from, to
#   Returns: list of alert/threshold-crossing events in window
#   Used by HistoryChart for event markers
