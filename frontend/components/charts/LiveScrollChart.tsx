// 'use client'
// Reusable live-scrolling single-metric chart component.
//
// Props:
//   data: { timestamp: number; value: number }[]
//   label: string
//   unit: string
//   color: string
//   warningThreshold?: number
//   criticalThreshold?: number
//   windowSeconds?: number    (default 60)
//   height?: number
//
// Renders a Recharts LineChart that:
//   - Slices data to last windowSeconds automatically
//   - Draws horizontal ReferenceLine for warning (amber dashed) and critical (red dashed)
//   - Custom dot: only renders latest point dot, suppresses others for performance
//   - isAnimationActive: false (real-time data — animation causes lag)
//   - Responsive via ResponsiveContainer
