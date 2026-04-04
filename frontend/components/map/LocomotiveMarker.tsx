// 'use client'
// Custom Leaflet marker for a single locomotive in the fleet.
//
// Uses a custom DivIcon with:
//   - Train SVG icon (larger + label for OWN locomotive, smaller for others)
//   - Color ring reflecting current health grade (HEALTH_GRADE_COLORS)
//   - Proximity warning ring: amber/red outer glow if this train is in a proximity alert
//   - Tooltip on hover: locomotive ID, speed, health grade, distance to nearest train
//   - Direction indicator: small arrow showing bearing from snapToRoute()
//
// Props:
//   position: [lat: number, lng: number]
//   healthGrade: 'A' | 'B' | 'C' | 'D' | 'E'
//   speed: number
//   locomotiveId: string
//   isOwn: boolean                          — renders larger with operator name label
//   proximityAlert?: 'warning' | 'critical' | null
