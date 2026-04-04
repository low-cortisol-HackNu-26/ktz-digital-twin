// 'use client'
// Export button with format selector (PDF / CSV).
//
// Props:
//   locomotiveId: string
//   from: number   (Unix ms)
//   to: number     (Unix ms)
//
// Behavior:
//   1. User picks format (PDF or CSV) via dropdown
//   2. POST /api/export → receives { jobId }
//   3. Polls GET /api/export/{jobId} every 2s (TanStack Query, refetchInterval)
//      until status === 'done'
//   4. On done: triggers file download via window.location or hidden <a> tag
//   5. Loading state: spinner in button, "Preparing export..."
//   6. Error state: toast notification
