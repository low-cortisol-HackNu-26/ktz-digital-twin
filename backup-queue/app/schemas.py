"""Request/response schemas for backup queue service."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class TelemetryEventPayload(BaseModel):
    """Raw telemetry event from client or simulator."""

    locomotive_id: str
    timestamp: datetime
    speed_kph: float
    target_speed_kph: float
    acceleration: float
    traction_mode: str
    # ... other fields omitted for brevity, can be extended
    
    class Config:
        extra = "allow"  # Allow additional fields


class QueueTelemetryRequest(BaseModel):
    """Request to queue telemetry locally."""

    locomotive_id: str
    event: dict[str, Any] = Field(..., description="Raw telemetry event")
    source: Optional[str] = Field("client", description="Source of event: client, simulator, train")


class QueueTelemetryResponse(BaseModel):
    """Response after queueing telemetry."""

    queued: bool
    queue_id: Optional[int] = None
    backend_status: str  # "reachable" | "unreachable"
    message: str


class QueueStatusResponse(BaseModel):
    """Current status of the backup queue."""

    queued_count: int = Field(..., description="Number of unsync'd events")
    synced_count: int = Field(..., description="Number of sync'd events (all time)")
    backend_reachable: bool
    last_sync_at: Optional[datetime] = None
    last_error: Optional[str] = None
    oldest_queued_at: Optional[datetime] = None


class SyncResponse(BaseModel):
    """Result of manual sync operation."""

    synced_count: int = Field(..., description="Number of events successfully synced")
    failed_count: int = Field(..., description="Number of events that failed to sync")
    remaining_count: int = Field(..., description="Number of events still in queue")
    backend_reachable: bool


class HealthResponse(BaseModel):
    """Service health status."""

    status: str  # "healthy" | "degraded" | "unhealthy"
    backend_reachable: bool
    dispatcher_reachable: bool
    queue_size: int
    dispatcher_queue_size: int
    uptime_seconds: float


# ---------------------------------------------------------------------------
# Dispatcher queue schemas
# ---------------------------------------------------------------------------

class QueueDispatcherRequest(BaseModel):
    """Queue any event for the dispatcher."""

    event_type: str = Field(
        ...,
        description="Type of event: 'warning', 'fleet_update', etc.",
        examples=["warning"],
    )
    endpoint: str = Field(
        ...,
        description="Dispatcher endpoint path to POST to, e.g. /api/warnings",
        examples=["/api/warnings"],
    )
    payload: dict[str, Any] = Field(..., description="JSON body to forward to dispatcher")
    auth_token: Optional[str] = Field(
        None,
        description="Bearer token to authenticate with dispatcher. If omitted, service token is used.",
    )
    source: Optional[str] = Field("client", description="Origin of the event")
    target_url: Optional[str] = Field(
        None,
        description="Full target URL override. If set, forwards here instead of dispatcher_url+endpoint.",
        examples=["http://backend:8000/api/sync/users"],
    )


class QueueDispatcherResponse(BaseModel):
    """Response after queuing a dispatcher event."""

    queued: bool
    queue_id: Optional[int] = None
    dispatcher_status: str  # "reachable" | "unreachable"
    message: str


class DispatcherQueueStatusResponse(BaseModel):
    """Status of the dispatcher-bound queue."""

    queued_count: int
    synced_count: int
    dispatcher_reachable: bool
    last_sync_at: Optional[datetime] = None
    last_error: Optional[str] = None
    oldest_queued_at: Optional[datetime] = None


class DispatcherSyncResponse(BaseModel):
    synced_count: int
    failed_count: int
    remaining_count: int
    dispatcher_reachable: bool


class QueueItemDetail(BaseModel):
    id: int
    event_type: str
    endpoint: str
    source: str
    payload: dict[str, Any]
    target_url: Optional[str]
    created_at: datetime
    synced_at: Optional[datetime]
    retry_count: int
    error_message: Optional[str]

    class Config:
        from_attributes = True


class TelemetryItemDetail(BaseModel):
    id: int
    locomotive_id: str
    source: str
    event_data: dict[str, Any]
    created_at: datetime
    synced_at: Optional[datetime]
    retry_count: int
    error_message: Optional[str]

    class Config:
        from_attributes = True
