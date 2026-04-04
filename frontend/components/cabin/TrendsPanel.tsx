// 'use client'
// Multi-line live scrolling trends chart — spans 2 columns in the cabin grid.
//
// Features:
//   - Recharts ComposedChart with synchronized X axis (time)
//   - Lines: speed, engineTemp, fuelLevel (normalized 0–100 for same scale)
//   - Y-axis shows both normalized % and a secondary axis with real units
//   - Auto-scrolling window: shows last N minutes (default 5), selectable 1/5/15
//   - Zoom: Recharts ReferenceArea drag-to-zoom; double-click to reset
//   - Tooltips: custom formatter shows all values at cursor time
//   - Reference lines for thresholds (warning / critical)
//   - "Add parameter" button: checkbox dropdown to toggle which params are shown
//
// Data source: useTelemetry(s => s.history)
