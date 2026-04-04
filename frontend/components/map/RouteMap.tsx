// 'use client'
// Leaflet map showing the full fleet's route and all locomotive positions.
//
// Implementation:
//   - Dynamic import (next/dynamic, ssr: false) — Leaflet requires browser
//   - Tile layer: dark railway tile layer (always dark — fixed HMI theme)
//   - Polyline: shared route GeoJSON (loaded from /api/route via fetchRouteGeoJSON)
//   - <LocomotiveMarker /> for EVERY locomotive in fleetStore.getAllPositions()
//     (own locomotive highlighted with larger marker and label)
//   - Proximity warnings: draw red/amber line segment between any two trains
//     whose distance < PROXIMITY_WARNING_KM (calculated via proximity.ts calculateProximities)
//   - Speed-limit zone highlights: colored segments from route GeoJSON properties
//   - Auto-pan: map follows OWN locomotive unless user has manually panned
//   - Proximity alert toast: fires when any pair drops below PROXIMITY_CRITICAL_KM
//
// Data sources:
//   fleetStore.getAllPositions() — all train positions
//   proximity.ts — distance calculations via @turf/turf
//   Own locomotive: fleetStore.getOwnState()?.latest
