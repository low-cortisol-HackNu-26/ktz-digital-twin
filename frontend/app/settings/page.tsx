// Settings page — Admin role only (check session.user.role; 403 for others).
//
// Sections:
//   1. Threshold editor:
//      - Table of parameters with editable normal/warning/critical ranges and weights
//      - "Save" → PUT /api/thresholds (reloads config on backend without restart)
//   2. Simulator controls:
//      - Start/stop simulator, select scenario (normal / anomaly / highload)
//      - Set Hz rate for highload test
//   3. Alert notification settings:
//      - Enable/disable toast notifications per severity
//   4. Account info (read-only): name, role, Keycloak ID
