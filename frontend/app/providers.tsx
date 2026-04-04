// Client-side provider tree — rendered inside root layout.
//
// Providers to compose (outermost → innermost):
//   1. CardAuthProvider (local context, see lib/cardAuth.ts)
//        - Reads token from sessionStorage on mount
//        - Exposes user: UserInfo | null and logout()
//        - Redirects to /login if token missing or expired
//   2. QueryClientProvider (TanStack Query) — supplies useQuery/useMutation
//   3. ThemeProvider (shadcn next-themes, defaultTheme="dark") — HMI is dark by default
//
// Accept children: React.ReactNode
// Mark with 'use client'
//
// Note: No NextAuth SessionProvider — auth is handled by CardAuthProvider.
