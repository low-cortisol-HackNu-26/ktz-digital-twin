// Card-based authentication client.
// Replaces NextAuth.js — auth is a simple card UID → JWT exchange.
//
// authenticateCard(cardUID: string): Promise<AuthResult>
//   POST /api/auth/card  with body { cardUID }
//   On success: receives { token: string; expiresAt: number; user: UserInfo }
//   Stores token in sessionStorage (not localStorage — clears on tab close)
//   Returns AuthResult
//
// getToken(): string | null
//   Reads token from sessionStorage
//   Returns null if missing or expired (checks expiresAt)
//
// logout(): void
//   Clears token from sessionStorage
//   Redirects to /login
//
// getUser(): UserInfo | null
//   Decodes JWT payload (no verification — trust server-issued token)
//   Returns { sub, name, role, locomotiveId } or null
//
// isAuthenticated(): boolean
//   Returns getToken() !== null
//
// UserInfo:
//   sub: string          (card UID hash)
//   name: string         (operator name from card registry)
//   role: 'Machinist' | 'Dispatcher' | 'Admin'
//   locomotiveId: string (assigned locomotive, set in card registry)
