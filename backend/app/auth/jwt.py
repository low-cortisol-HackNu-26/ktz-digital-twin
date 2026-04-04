# JWT issuance and verification — self-contained, no external identity provider.
# Uses python-jose with HS256 (HMAC-SHA256) and SECRET_KEY from settings.
#
# issue_token(card: CardRecord) -> str
#   Builds JWT payload:
#     sub: str(card.id)
#     name: card.operator_name
#     role: card.role
#     locomotiveId: card.assigned_locomotive_id
#     jti: str(uuid4())    (unique token ID, used for logout blocklist)
#     iat: now (UTC)
#     exp: now + timedelta(hours=8)   (one shift)
#   Signs with settings.SECRET_KEY using HS256 (python-jose jwt.encode)
#   Returns encoded token string
#
# verify_token(token: str) -> UserClaims
#   Decodes JWT using settings.SECRET_KEY
#   Checks: expiry, algorithm is HS256
#   Checks jti is NOT in Redis blocklist (SET "blocklist:{jti}")
#   Raises HTTPException(401) on any failure
#   Returns UserClaims (from schemas/auth.py)
#
# block_token(jti: str, ttl_seconds: int) -> None
#   SET "blocklist:{jti}" in Redis with TTL = remaining token lifetime
#   Called by POST /api/auth/logout
