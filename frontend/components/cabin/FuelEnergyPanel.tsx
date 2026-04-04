// 'use client'
// Fuel and energy panel card.
//
// Displays:
//   - Fuel level: vertical tank gauge (SVG or CSS), current liters + percentage
//   - Fuel consumption rate: numeric (L/h) with trend arrow (up/down vs 5-min avg)
//   - Estimated range: derived = fuelLevel / consumptionRate * speed (km remaining)
//   - Low fuel alert highlight when level < threshold from thresholds.json
//
// Data source: useTelemetry(s => pick(s.latest, ['fuelLevel','fuelConsumptionRate']))
