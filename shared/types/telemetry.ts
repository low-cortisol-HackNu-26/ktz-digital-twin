// Shared TypeScript types — used by frontend directly, and as source-of-truth
// for backend Pydantic schema codegen (openapi-typescript or manual sync).
//
// Types to define:
//
// TelemetryPacket:
//   locomotiveId: string
//   timestamp: number          (Unix ms)
//   speed: number              (km/h)
//   throttle: number           (0–100 %)
//   fuelLevel: number          (liters or %)
//   fuelConsumptionRate: number(L/h)
//   engineTemp: number         (°C)
//   oilPressure: number        (bar)
//   brakePressure: number      (bar)
//   voltage: number            (V)
//   current: number            (A)
//   latitude: number
//   longitude: number
//   alerts: AlertCode[]
//   rawJson?: Record<string, unknown>   (passthrough for extra fields)
//
// AlertCode: string enum of known fault codes (e.g. "ENG_OVERHEAT", "LOW_FUEL", ...)
//
// HealthIndex:
//   score: number              (0–100)
//   grade: 'A' | 'B' | 'C' | 'D' | 'E'
//   category: 'NORMAL' | 'WARNING' | 'CRITICAL'
//   factors: HealthFactor[]    (top-5 contributing parameters)
//   timestamp: number
//
// HealthFactor:
//   parameter: string
//   value: number
//   contribution: number       (positive = good, negative = penalty)
//   label: string              (human-readable)
