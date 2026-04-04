// 'use client'
// Active alerts panel — top-right of cabin grid.
//
// Displays:
//   - Scrollable list of active alerts, sorted by severity (critical first)
//   - Each alert row: severity icon (color-coded), alert code, human label,
//     timestamp, "Acknowledge" button
//   - Empty state: large green checkmark + "All systems normal"
//   - Alert count badge on the panel header (red if any critical)
//   - On new critical alert: browser Notification API + audible beep (optional)
//
// Data source: alertStore (activeAlerts)
