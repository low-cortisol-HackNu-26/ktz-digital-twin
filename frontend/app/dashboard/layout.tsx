// Dashboard layout — wraps all /dashboard/* pages.
// Mark with 'use client'.
//
// Responsibilities:
//   - Read user from CardAuthProvider; if null → redirect to /login
//   - Seed fleetStore.setOwnLocomotive(user.locomotiveId) on mount
//   - Render fixed top bar (fixed px height): KTZ logo, operator name + role badge, logout button
//   - Render <ConnectionStatus> for own locomotive (live/reconnecting/offline dot)
//   - Provide <WebSocketProvider> — opens WS for ALL known locomotives (fleet feed)
//     so fleetStore receives packets for every train, not just the operator's own
//   - Layout: fixed 1920×1080 viewport assumption, overflow hidden, dark cabin background
