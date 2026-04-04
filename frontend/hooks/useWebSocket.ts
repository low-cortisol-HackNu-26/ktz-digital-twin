// 'use client'
// Custom hook: manages WebSocket connections for the full fleet.
//
// Arguments: locomotiveIds: string[]
//
// Behavior:
//   - Opens one WS connection per locomotiveId in the array
//   - Attaches JWT from cardAuth.getToken() as ?token= query param
//   - On message for any locomotive: parses TelemetryPacket JSON,
//     dispatches to fleetStore.addPacket(locomotiveId, packet)
//   - Reconnect with exponential backoff per connection (WS_RECONNECT_DELAYS)
//   - Tracks per-locomotive connectionStatus in fleetStore
//   - Runs tickStaleness() on a 5s interval to detect dead connections
//   - Cleans up all connections on unmount
//
// Returns: { statuses: Record<string, 'connecting'|'live'|'reconnecting'|'offline'> }
