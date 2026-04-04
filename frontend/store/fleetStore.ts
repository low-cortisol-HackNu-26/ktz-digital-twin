// Zustand fleet state manager — holds telemetry and health for ALL locomotives.
// This replaces the single-locomotive telemetryStore as the primary data store.
//
// State shape:
//   locomotives: Record<locomotiveId, LocomotiveState>
//   ownLocomotiveId: string | null       — the locomotive this operator is assigned to
//   activeLocomotiveId: string | null    — which one is displayed in the main cabin view
//
// LocomotiveState:
//   id: string
//   name: string
//   latest: TelemetryPacket | null
//   history: TelemetryPacket[]           — circular buffer, last 300 packets
//   healthIndex: HealthIndex | null
//   connectionStatus: 'live' | 'stale' | 'offline'
//   lastUpdated: number | null
//   alerts: Alert[]
//
// Actions:
//   addPacket(locomotiveId: string, packet: TelemetryPacket): void
//     - Creates entry if locomotiveId is new
//     - Applies EMA smoothing, deduplicates, manages buffer
//     - Updates connectionStatus → 'live', sets lastUpdated
//
//   setHealthIndex(locomotiveId: string, hi: HealthIndex): void
//
//   setOwnLocomotive(id: string): void
//   setActiveLocomotive(id: string): void
//
//   tickStaleness(): void
//     - Called every 5s; sets status 'stale' if lastUpdated > 3s ago, 'offline' if > 15s
//     - Intended to be called from a setInterval in the WS provider
//
//   getOwnState(): LocomotiveState | null  — selector shorthand
//   getAllPositions(): { id: string; lat: number; lng: number; grade: string }[]
//     — used by RouteMap to render all fleet markers
