# FastAPI dependency functions (used in route handlers via Depends()).
#
# get_db() -> AsyncSession
#   Yields an async SQLAlchemy session; commits on success, rolls back on exception.
#
# get_current_user(token: str = Depends(oauth2_scheme)) -> UserClaims
#   Reads Bearer token from Authorization header (OAuth2PasswordBearer scheme).
#   Calls auth/jwt.py verify_token() — internal HS256 verification, no external call.
#   Raises HTTP 401 if invalid/expired/blocklisted.
#   Returns UserClaims(sub, name, role, locomotiveId, jti).
#
# require_role(*roles: str)
#   Returns a dependency that checks current_user.role is in roles.
#   Raises HTTP 403 if not.
#   Usage: Depends(require_role("Admin", "Dispatcher"))
#
# get_redis() -> Redis
#   Returns the shared aioredis client from app state.
