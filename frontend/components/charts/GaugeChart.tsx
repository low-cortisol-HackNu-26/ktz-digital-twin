// 'use client'
// Reusable semicircular gauge component (used in PressureTempPanel, ElectricsPanel).
//
// Props:
//   value: number
//   min: number
//   max: number
//   unit: string
//   label: string
//   zones: { from: number; to: number; color: string }[]   (color bands)
//   size?: 'sm' | 'md' | 'lg'
//
// Implementation: SVG arc paths for zone bands + needle line.
// No external chart library — pure SVG for precise control.
// Animates needle with CSS transition on value change.
