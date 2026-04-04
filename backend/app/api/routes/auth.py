# Card authentication route.
#
# POST /api/auth/card
#   Body: { cardUID: str }
#   No auth required (this IS the auth endpoint)
#   Steps:
#     1. Hash cardUID (SHA-256) and look up in cards table (models/card.py)
#     2. If not found: return HTTP 401 "Card not registered"
#     3. If found: issue JWT via auth/jwt.py with claims:
#          sub: card.id (UUID)
#          name: card.operator_name
#          role: card.role
#          locomotiveId: card.assigned_locomotive_id
#          exp: now + 8h (one shift)
#     4. Return { token: str; expiresAt: int; user: { name, role, locomotiveId } }
#
# POST /api/auth/logout
#   Auth: valid JWT required
#   Adds token jti to a Redis blocklist (TTL = remaining token lifetime)
#   Returns 200 OK  (client clears sessionStorage)
#
# GET /api/auth/me
#   Auth: valid JWT required
#   Returns current UserClaims decoded from token
