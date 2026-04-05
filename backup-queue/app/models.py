"""SQLAlchemy models for backup queue."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class TelemetryQueueItem(Base):
    """Queued telemetry event waiting to be synced to backend."""

    __tablename__ = "telemetry_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    locomotive_id = Column(String(50), nullable=False, index=True)
    
    # Raw event data as JSON
    event_data = Column(JSON, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    synced_at = Column(DateTime(timezone=True), nullable=True)
    last_retry_at = Column(DateTime(timezone=True), nullable=True)
    
    # Retry tracking
    retry_count = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Metadata
    source = Column(String(50), default="client", nullable=False)  # "client" | "simulator" | "train"
    
    def __repr__(self) -> str:
        return f"<TelemetryQueueItem(id={self.id}, loco={self.locomotive_id}, synced={self.synced_at is not None})>"
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "locomotive_id": self.locomotive_id,
            "event_data": self.event_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "synced_at": self.synced_at.isoformat() if self.synced_at else None,
            "retry_count": self.retry_count,
            "error_message": self.error_message,
        }


class DispatcherQueueItem(Base):
    """Client event destined for the dispatcher, buffered until dispatcher is reachable."""

    __tablename__ = "dispatcher_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Which dispatcher endpoint to POST to, e.g. /api/warnings
    endpoint = Column(String(128), nullable=False)

    # Human-readable event type: "warning", "fleet_update", etc.
    event_type = Column(String(50), nullable=False, index=True)

    # The JSON body to POST
    payload = Column(JSON, nullable=False)

    # JWT the client provided — used when forwarding to dispatcher
    auth_token = Column(Text, nullable=True)

    # Optional: full target URL (overrides dispatcher_url + endpoint)
    # e.g. "http://backend:8000/api/sync/users" for cross-service sync
    target_url = Column(Text, nullable=True)

    # Timestamps & retry tracking (same pattern as TelemetryQueueItem)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    synced_at = Column(DateTime(timezone=True), nullable=True)
    last_retry_at = Column(DateTime(timezone=True), nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)

    source = Column(String(50), default="client", nullable=False)
