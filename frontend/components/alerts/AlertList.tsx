// Scrollable alert history list — used in AlertsPanel and /history page.
//
// Props:
//   alerts: Alert[]
//   onAcknowledge?: (code: AlertCode) => void
//   maxHeight?: string   (CSS, default '300px')
//   showAcknowledged?: boolean  (default false — hides acknowledged alerts)
//
// Each row: <AlertBadge>, message, relative timestamp (e.g. "2 min ago"),
// optional acknowledge button, fade-out animation when acknowledged.
//
// Empty state: "No alerts" message with green check icon.
