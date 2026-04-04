// Utility functions shared across components.
//
// formatSpeed(kmh: number): string       — "120 km/h"
// formatTemp(celsius: number): string    — "92°C"
// formatPressure(bar: number): string    — "8.2 bar"
// formatFuel(liters: number): string     — "1,240 L"
// formatTimestamp(ms: number): string    — "14:32:07" (locale time)
// clampToRange(value, min, max): number
// cn(...classes): string                 — tailwind-merge + clsx helper (shadcn pattern)
// emaSmooth(prev: number, next: number, alpha: number): number
//   Exponential moving average: α * next + (1-α) * prev
