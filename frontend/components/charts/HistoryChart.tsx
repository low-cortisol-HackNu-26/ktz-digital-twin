// 'use client'
// Static history chart for the /history page.
//
// Props:
//   data: TelemetryPacket[]
//   parameters: string[]       (which fields to plot)
//   events: HistoryEvent[]     (alert/threshold events to mark as vertical lines)
//   onScrub: (timestamp: number) => void   (called on playback slider change)
//
// Features:
//   - Recharts ComposedChart with zoom via ReferenceArea drag
//   - ReferenceLine for each event in events[]
//   - Brush component at bottom for overview navigation
//   - Synchronized cursor across multiple chart instances (if multiple charts on page)
//   - "Reset zoom" button
