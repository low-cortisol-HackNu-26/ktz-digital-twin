// Zustand store for alerts and health index.
//
// State shape:
//   activeAlerts: Alert[]           — currently firing alerts (deduped by code)
//   healthIndex: HealthIndex | null — latest computed health index
//   alertHistory: Alert[]           — all alerts in session, for the alerts panel log
//
// Alert type:
//   code: AlertCode
//   severity: 'info' | 'warning' | 'critical'
//   message: string
//   timestamp: number
//   acknowledgedAt?: number
//
// Actions:
//   setHealthIndex(hi: HealthIndex): void
//   addAlert(alert: Alert): void        — also triggers toast if severity >= warning
//   acknowledgeAlert(code: AlertCode): void
//   clearAlerts(): void
