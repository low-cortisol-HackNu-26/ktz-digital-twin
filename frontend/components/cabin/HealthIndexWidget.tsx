// 'use client'
// The primary widget — shown large in the top-left of the cabin grid.
//
// Displays:
//   - Score (0–100) as a large radial gauge (Recharts RadialBarChart or custom SVG arc)
//   - Grade badge (A–E) with background color from HEALTH_GRADE_COLORS
//   - Category label: "NORMAL" / "WARNING" / "CRITICAL" with matching border glow
//   - Top-5 factors list: parameter name, contribution bar (positive=green, negative=red)
//   - "Last updated" timestamp
//
// Animations:
//   - Score arc animates smoothly on each update (CSS transition)
//   - CRITICAL category: card border pulses (critical-blink keyframe)
//
// Data source: useHealthIndex() hook
