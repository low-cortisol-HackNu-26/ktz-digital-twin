# Backup Queue Service

**Status:** ✅ Phase 1 Complete

## Overview

The Backup Queue Service is an offline-first telemetry buffering microservice that enables train clients and simulators to queue telemetry locally when the backend is unreachable, then automatically sync when connectivity is restored.

## Features

- **Local Buffering:** SQLite-backed queue for storing telemetry when offline
- **Automatic Sync:** Background task attempts sync every 30 seconds
- **Exponential Backoff:** Retry strategy with backoff from 1s to 30 minutes
- **Health Monitoring:** `/health` endpoint with service status
- **Queue Status:** Real-time visibility into queue size and sync state
- **Manual Sync:** Trigger sync on demand without waiting for background task

## API Endpoints

### POST `/api/queue/telemetry`
Queue a telemetry event locally.

**Request:**
```json
{
  "locomotive_id": "KZ8A-0001",
  "event": {
    "locomotive_id": "KZ8A-0001",
    "timestamp": "2026-04-05T12:00:00Z",
    "speed_kph": 85.5,
    "target_speed_kph": 100,
    "acceleration": 1.2,
    "traction_mode": "traction"
  },
  "source": "simulator"
}
```

**Response:**
```json
{
  "queued": true,
  "queue_id": 1,
  "backend_status": "reachable|unreachable",
  "message": "Event queued for later sync"
}
```

### GET `/api/queue/status`
Get current queue status.

**Response:**
```json
{
  "queued_count": 5,
  "synced_count": 150,
  "backend_reachable": true,
  "last_sync_at": "2026-04-05T12:15:00Z",
  "last_error": null,
  "oldest_queued_at": "2026-04-05T12:10:00Z"
}
```

### POST `/api/queue/sync`
Manually trigger sync of queued events.

**Response:**
```json
{
  "synced_count": 5,
  "failed_count": 0,
  "remaining_count": 0,
  "backend_reachable": true
}
```

### GET `/health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy|degraded|unhealthy",
  "backend_reachable": true,
  "queue_size": 0,
  "uptime_seconds": 125.5
}
```

### GET `/docs`
Interactive Swagger API documentation.

## Architecture

```
Train Client / Simulator
        ↓
POST /api/queue/telemetry
        ↓
Backup Queue Service
├─→ SQLite (local storage)
│
├─→ Background Sync Task (every 30s)
│   └─→ Backend /api/ingest/telemetry (if reachable)
│
└─→ Exponential Backoff Retry
    (1s → 5s → 30s → 5m → 30m)
```

## Configuration

### Environment Variables

```bash
BACKUP_DB_URL=sqlite+aiosqlite:///./backup_queue.db
# Or PostgreSQL: postgresql+asyncpg://user:pass@localhost/db
```

### Running Locally

```bash
cd backup-queue
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8001
```

### Docker Compose

Service is included in `docker-compose.yml`:
- Port: 8001
- Database: SQLite at `/app/backup_queue.db` (volume-mounted)
- Auto-starts with backend

## Data Model

### TelemetryQueueItem (SQLite)

```sql
CREATE TABLE telemetry_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    locomotive_id TEXT NOT NULL,
    event_data JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP,
    last_retry_at TIMESTAMP,
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    source TEXT DEFAULT 'client'
);

CREATE INDEX idx_locomotive_synced ON telemetry_queue(locomotive_id, synced_at);
```

## Sync Algorithm

1. **Check Backend Health:** Health check to `http://backend:8000/api/health`
2. **Get Unsync'd Items:** Fetch up to 50 events from queue where `synced_at IS NULL`
3. **Attempt Upload:** POST each item to `http://backend:8000/api/ingest/telemetry`
4. **Success:** Mark item with `synced_at` timestamp
5. **Failure:** Increment `retry_count`, calculate backoff, update `error_message`
6. **Background Loop:** Repeat every 30 seconds indefinitely

### Exponential Backoff Formula

```
backoff_seconds = min(30*60, 1 * 2^retry_count)
```

- Retry 0: 1s
- Retry 1: 2s
- Retry 2: 4s
- Retry 3: 8s
- Retry 4: 16s
- Retry 5: 32s
- Retry 10: 1024s ≈ 17 minutes
- Retry 15: 32768s = 30 minutes (capped)

## Testing

### Queue an Event
```bash
curl -X POST http://localhost:8001/api/queue/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "locomotive_id": "KZ8A-0001",
    "event": {
      "locomotive_id": "KZ8A-0001",
      "timestamp": "2026-04-05T12:00:00Z",
      "speed_kph": 85.5,
      "target_speed_kph": 100,
      "acceleration": 1.2,
      "traction_mode": "traction"
    }
  }'
```

### Check Status
```bash
curl http://localhost:8001/api/queue/status | jq .
```

### Manually Trigger Sync
```bash
curl -X POST http://localhost:8001/api/queue/sync | jq .
```

### Check Health
```bash
curl http://localhost:8001/health | jq .
```

## Deployment

### Docker
```bash
# Build
docker compose build backup-queue

# Run
docker compose up -d backup-queue

# Logs
docker logs hacknu26-backup-queue-1 -f
```

### Health Check
The service is production-ready. Monitor:
- `/health` endpoint for service status
- `/api/queue/status` for queue depth
- Docker container logs for sync errors

## Future Enhancements

### Phase 2: Kafka Integration
- Publish queued events to Kafka topic `telemetry.backlog`
- Enable multiple consumers (dispatcher, analytics)
- Event replay capability

### Phase 3: Batch Uploading
- Group events by locomotive and time window
- Single POST with array of events
- Endpoint: `POST /api/ingest/telemetry/batch`

### Advanced Features
- Message encryption for sensitive data
- Compression for large batches
- Metrics/Prometheus integration
- Maximum queue size limits
- Dead letter queue for permanently failed events

## Known Issues / Notes

- Backend health check uses `http://backend:8000` (Docker internal DNS)
- SQLite file location: `/app/backup_queue.db` (inside container)
- No authentication currently (add if needed)
- Single-threaded sync (sufficient for current scale)

## Architecture Fit

```
System Overview:
┌─────────────────────────────────────────────┐
│  Train/Simulator Client                     │
│  (with backup-queue SDK)                    │
└──────────┬──────────────────────────────────┘
           │
           ├─→ POST /api/queue/telemetry (backup-queue)
           │   ↓
           │   Local SQLite buffer
           │
           └─→ POST /api/ingest/telemetry (backend)
               (when online)
               ↓
               Backend App (PostgreSQL, Redis, WebSocket)
```

The backup-queue service fits between the client and backend, enabling offline-first applications.
