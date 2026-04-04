# Pydantic v2 schemas for card authentication API.
#
# class CardAuthRequest(BaseModel):
#   cardUID: str   (raw UID from reader; backend hashes it immediately, never stores raw)
#
# class UserInfo(BaseModel):
#   sub: str             (UUID of CardRecord)
#   name: str
#   role: Literal['Machinist', 'Dispatcher', 'Admin']
#   locomotiveId: str | None
#
# class CardAuthResponse(BaseModel):
#   token: str           (signed JWT, issued by auth/jwt.py)
#   expiresAt: int       (Unix ms)
#   user: UserInfo
#
# class UserClaims(BaseModel):
#   sub: str
#   name: str
#   role: str
#   locomotiveId: str | None
#   jti: str             (used for logout blocklist)
#   exp: int
