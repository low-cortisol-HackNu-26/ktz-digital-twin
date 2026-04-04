// 'use client'
// Speed panel card.
//
// Displays:
//   - Current speed: large numeric readout (numeric-readout class), km/h
//   - Throttle position: horizontal progress bar (0–100%)
//   - Mini sparkline (last 60 seconds of speed data) — Recharts LineChart
//   - Speed limit indicator if backend provides route limit for current segment
//   - Color coding: green=normal, amber=approaching limit, red=over limit
//
// Data source: useTelemetry(s => s.latest?.speed)
