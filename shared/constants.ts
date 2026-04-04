// Shared constants — imported by frontend; kept in sync with backend manually.
//
// Export:
//
// ALERT_CODES: Record<string, { label: string; severity: 'info' | 'warning' | 'critical' }>
//   Map of fault code → human label + severity
//   e.g. ENG_OVERHEAT, LOW_FUEL, BRAKE_FAULT, LOW_OIL_PRESSURE, HIGH_CURRENT, ...
//
// WS_RECONNECT_DELAYS: number[]
//   Exponential backoff delay sequence in ms for WebSocket reconnect attempts
//   e.g. [1000, 2000, 4000, 8000, 16000, 30000]
//
// HISTORY_WINDOWS: { label: string; minutes: number }[]
//   Options for the history replay selector
//   e.g. [5, 15, 30, 60] minutes
//
// HEALTH_GRADE_COLORS: Record<'A'|'B'|'C'|'D'|'E', string>
//   Tailwind color tokens or hex values for each grade badge
//
// TELEMETRY_UPDATE_HZ: number
//   Expected packet rate from simulator (default 1); used for chart buffer sizing
