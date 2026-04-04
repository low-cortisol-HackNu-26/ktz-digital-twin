// 'use client'
// Reads the latest HealthIndex from Zustand alertStore.
//
// Returns:
//   healthIndex: HealthIndex | null
//   grade: 'A' | 'B' | 'C' | 'D' | 'E' | null
//   category: 'NORMAL' | 'WARNING' | 'CRITICAL' | null
//   topFactors: HealthFactor[]    (sorted by |contribution| desc, take first 5)
//   gradeColor: string            (Tailwind class from HEALTH_GRADE_COLORS constant)
//
// The health index is computed by the backend and arrives via the WS packet or
// a separate SSE stream; this hook just selects it from the store.
