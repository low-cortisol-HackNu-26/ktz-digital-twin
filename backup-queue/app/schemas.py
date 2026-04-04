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
    queue_size: int
    uptime_seconds: float
