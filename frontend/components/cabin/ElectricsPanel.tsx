// 'use client'
// Electrical systems panel card.
//
// Displays:
//   - Voltage (V): horizontal bar gauge with min/max markers
//   - Current (A): numeric with trend indicator
//   - Power (kW): derived = voltage * current / 1000
//   - Status icons for traction motor, compressor, auxiliary systems
//     (green=OK, red=fault based on active alert codes)
//
// Data source: useTelemetry(s => pick(s.latest, ['voltage','current']))
//              + useAlerts() for system fault icons
