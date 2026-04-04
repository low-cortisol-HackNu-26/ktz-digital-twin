from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import perf_counter


@dataclass
class ServiceMetrics:
    started_at: float = field(default_factory=perf_counter)
    valid_events_count: int = 0
    invalid_events_count: int = 0
    dropped_events_count: int = 0
    db_write_latency_ms: float = 0.0
    redis_publish_latency_ms: float = 0.0
    last_event_timestamp: datetime | None = None
    per_locomotive_last_seen: dict[str, datetime] = field(default_factory=dict)

    def mark_valid(self, locomotive_id: str, ts: datetime) -> None:
        self.valid_events_count += 1
        self.last_event_timestamp = ts
        self.per_locomotive_last_seen[locomotive_id] = ts

    def mark_invalid(self, count: int = 1) -> None:
        self.invalid_events_count += count

    def mark_dropped(self, count: int = 1) -> None:
        self.dropped_events_count += count

    def ingest_rate_per_sec(self) -> float:
        elapsed = max(perf_counter() - self.started_at, 0.001)
        return self.valid_events_count / elapsed

    def to_dict(self, ws_clients_count: int) -> dict:
        return {
            "ingest_rate_per_sec": round(self.ingest_rate_per_sec(), 3),
            "valid_events_count": self.valid_events_count,
            "invalid_events_count": self.invalid_events_count,
            "dropped_events_count": self.dropped_events_count,
            "db_write_latency_ms": round(self.db_write_latency_ms, 3),
            "ws_clients_count": ws_clients_count,
            "redis_publish_latency_ms": round(self.redis_publish_latency_ms, 3),
            "last_event_timestamp": self.last_event_timestamp,
            "per_locomotive_last_seen": {
                k: v.astimezone(timezone.utc).isoformat() for k, v in self.per_locomotive_last_seen.items()
            },
        }


metrics = ServiceMetrics()
