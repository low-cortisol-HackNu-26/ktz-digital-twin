"""Dispatcher Pydantic schemas."""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ============================================================================
# Auth
# ============================================================================

class LoginRequest(BaseModel):
    uid: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    uid: str = Field(..., min_length=1, max_length=64, description="Company/operator ID used for login")
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=1, max_length=256)
    role: Literal["Machinist", "Dispatcher", "Admin"] = Field("Machinist")
    locomotive_id: Optional[str] = Field(None, max_length=64)


class DriverInfo(BaseModel):
    id: str
    company_id: str
    name: str
    role: str
    locomotive_id: Optional[str] = None

    class Config:
        from_attributes = True


class SessionResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: int
    session_id: str
    driver: DriverInfo


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


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


# ============================================================================
# User Management
# ============================================================================

class UserInfo(BaseModel):
    id: str
    company_id: str
    name: str
    role: str
    locomotive_id: Optional[str]
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True


class ListUsersResponse(BaseModel):
    users: list[UserInfo]
    total_count: int


# ============================================================================
# Warning/Alert Management
# ============================================================================

class ManualWarningCreateRequest(BaseModel):
    target_type: Literal["locomotive", "route_segment"]
    target_id: str = Field(..., min_length=1, max_length=128)
    warning_type: Literal[
        "weather",
        "track",
        "maintenance_zone",
        "temporary_speed_limit",
        "manual_caution",
    ]
    severity: Literal["info", "warning", "critical"]
    title: str = Field(..., min_length=1, max_length=128)
    message: str = Field(..., min_length=1)
    recommended_action: str = Field(..., min_length=1)
    duration_seconds: int = Field(..., ge=1, le=86400)
    source: Literal["dispatcher", "admin"] = "dispatcher"
    created_by: Optional[str] = Field(None, max_length=128)
    metadata: Optional[dict[str, Any]] = None


class ManualWarningCreateResponse(BaseModel):
    warning_id: str
    target_type: str
    target_id: str
    affected_locomotive_ids: list[str]
    expires_at: datetime


class WarningResponse(BaseModel):
    warning_id: str
    locomotive_id: str
    rule_id: str
    source: str
    target_type: str
    target_id: str
    severity: str
    title: str
    message: str
    recommended_action: str
    created_by: Optional[str] = None
    active: bool
    first_seen_at: datetime
    last_seen_at: datetime
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ListWarningsResponse(BaseModel):
    warnings: list[WarningResponse]
    total_count: int


# ============================================================================
# Fleet / Dashboard
# ============================================================================

class LocoStatusInfo(BaseModel):
    """Current locomotive position and status (Pydantic response model)."""
    locomotive_id: str
    lat: float
    lng: float
    speed_kph: float
    heading: Optional[float]
    route_code: Optional[str]
    route_name: Optional[str]
    is_online: bool
    active_warnings_count: int
    last_updated: datetime


class FleetStatusResponse(BaseModel):
    locomotives: list[LocoStatusInfo]
    total_locomotives: int
    locomotives_online: int
    active_warnings_count: int


class DashboardMetrics(BaseModel):
    total_locomotives: int
    online_locomotives: int
    total_active_warnings: int
    critical_warnings_count: int
    total_events_today: int
    avg_speed_kph: float
    system_uptime_seconds: float


class RouteInfo(BaseModel):
    code: str
    name: str
    total_length_km: float
    stations_count: int = 0

    class Config:
        from_attributes = True


class ListRoutesResponse(BaseModel):
    routes: list[RouteInfo]
    total_count: int
