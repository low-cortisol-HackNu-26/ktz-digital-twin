// History / Replay page.
//
// Features:
//   - Date-range picker (from / to) with preset buttons: last 5m, 15m, 30m, 1h
//   - Locomotive selector
//   - "Load" button → GET /api/history?locomotiveId=&from=&to= (TanStack Query)
//   - <HistoryChart /> — displays loaded time-series data, supports zoom/pan
//   - Event markers on chart (alerts, threshold crossings) shown as vertical lines
//   - Playback slider: scrub through the loaded window, panels update to that snapshot
//   - <ExportButton /> — triggers PDF or CSV export for the loaded window
//   - Summary table: min/max/avg for each parameter in the window
