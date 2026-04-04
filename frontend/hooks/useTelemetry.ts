// 'use client'
// Selector hook: reads telemetry state for a single locomotive from fleetStore.
//
// Arguments: locomotiveId?: string  (defaults to fleetStore.activeLocomotiveId)
//
// Returns:
//   latest: TelemetryPacket | null
//   history: TelemetryPacket[]      (last N packets from fleet circular buffer)
//   isStale: boolean                (connectionStatus !== 'live')
//
// Optionally accepts a selector function for fine-grained subscription
// (avoids re-renders for panels that only care about one parameter).
//
// Delegates to fleetStore — does not own any data itself.
