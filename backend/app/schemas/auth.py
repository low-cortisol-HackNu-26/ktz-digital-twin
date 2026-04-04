from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    uid: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    uid: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=256)
    role: Literal["Machinist", "Dispatcher", "Admin"]
    locomotive_id: str | None = Field(default=None, max_length=64)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class DriverInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: str
    name: str
    role: Literal["Machinist", "Dispatcher", "Admin"]
    locomotive_id: str | None = None


class SessionResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: int
    session_id: str
    driver: DriverInfo


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: int
    driver: DriverInfo


class OAuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LogoutResponse(BaseModel):
    detail: str


class TokenClaims(BaseModel):
    sub: str
    company_id: str
    name: str
    role: str
    locomotive_id: str | None = None
    sid: str
    jti: str
    token_type: Literal["access", "refresh"]
    iat: int
    exp: int
