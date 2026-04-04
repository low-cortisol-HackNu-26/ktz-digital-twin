// 'use client'
// Pressures and temperatures panel card.
//
// Displays a grid of gauge/numeric pairs for:
//   - Engine temperature (°C) — circular gauge
//   - Oil pressure (bar) — circular gauge
//   - Brake pressure (bar) — circular gauge
//   - Coolant temperature (°C) if available
//
// Each gauge uses color zones: green=normal, amber=warning, red=critical
// (zones derived from thresholds.json, loaded via GET /api/thresholds on mount)
//
// Tooltip on hover: shows normal range for that parameter
//
// Data source: useTelemetry(s => pick(s.latest, ['engineTemp','oilPressure','brakePressure']))
