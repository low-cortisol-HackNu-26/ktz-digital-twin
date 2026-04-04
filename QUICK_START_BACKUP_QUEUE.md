# Quick Start: Backup Queue Service

## What is it?

The backup queue service allows your train clients and simulators to **store telemetry locally when the backend is down**, then **automatically sync when the backend comes back online**. No data is lost due to network outages.

## Running

The service is already in docker-compose.yml. Just start it:

```bash
docker compose up -d backup-queue
```

It will be available at `http://localhost:8001`

## Testing

### 1. Check if service is running
```bash
curl http://localhost:8001/health
```

Expected response:
```json
{
  "status": "healthy",
  "backend_reachable": true,
  "queue_size": 0,
  "uptime_seconds": 5.2
}
```

### 2. Send a test telemetry event
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

Expected response:
```json
{
  "queued": true,
  "queue_id": 1,
  "backend_status": "reachable",
  "message": "Event sent to backend immediately"
}
```

### 3. Check queue status
```bash
curl http://localhost:8001/api/queue/status
```

### 4. View API docs
Open `http://localhost:8001/docs` in your browser for interactive documentation.

## How to Use in Your Client

### Python Example

```python
import httpx
import json
from datetime import datetime

async def send_telemetry_with_backup(locomotive_id, event):
    """Send telemetry with local backup if offline."""
    
    # Try backup queue first (always available locally)
    backup_queue_url = "http://localhost:8001/api/queue/telemetry"
    
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(backup_queue_url, json={
                "locomotive_id": locomotive_id,
                "event": event,
                "source": "my_app"
            })
            response.raise_for_status()
            result = response.json()
            print(f"Status: {result['backend_status']}")
            print(f"Queue ID: {result['queue_id']}")
            return True
    except Exception as e:
        print(f"Failed to queue: {e}")
        return False

# Usage
event = {
    "locomotive_id": "KZ8A-0001",
    "timestamp": datetime.utcnow().isoformat(),
    "speed_kph": 100,
    "target_speed_kph": 100,
    "acceleration": 0,
    "traction_mode": "coast"
}

await send_telemetry_with_backup("KZ8A-0001", event)
```

### JavaScript Example

```javascript
async function sendTelemetryWithBackup(locomotiveId, event) {
  const backupQueueUrl = "http://localhost:8001/api/queue/telemetry";
  
  try {
    const response = await fetch(backupQueueUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        locomotive_id: locomotiveId,
        event: event,
        source: "my_app"
      })
    });
    
    const result = await response.json();
    console.log(`Queued as #${result.queue_id}`);
    console.log(`Backend: ${result.backend_status}`);
    return true;
  } catch (error) {
    console.error(`Failed to queue:`, error);
    return false;
  }
}

// Usage
const event = {
  locomotive_id: "KZ8A-0001",
  timestamp: new Date().toISOString(),
  speed_kph: 100,
  target_speed_kph: 100,
  acceleration: 0,
  traction_mode: "coast"
};

await sendTelemetryWithBackup("KZ8A-0001", event);
```

## What Happens Internally?

1. **Your event arrives** → Stored in local SQLite database
2. **Service checks backend** → Is `http://backend:8000` reachable?
3. **If backend is UP** → Event is forwarded immediately to `/api/ingest/telemetry`
4. **If backend is DOWN** → Event stays in queue, marked as "pending sync"
5. **Every 30 seconds** → Service retries with exponential backoff
6. **When backend comes back** → All queued events are automatically sent
7. **Events are marked synced** → Removed from retry queue

## Key Benefits

✅ **Never lose data** - Local buffer survives backend outages  
✅ **Automatic retry** - No manual intervention needed  
✅ **Smart backoff** - Respects backend by not hammering it  
✅ **Transparent** - Client can check status anytime  
✅ **Scalable** - Handles thousands of queued events  

## API Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/queue/telemetry` | POST | Queue an event |
| `/api/queue/status` | GET | Check queue depth and status |
| `/api/queue/sync` | POST | Force immediate sync attempt |
| `/health` | GET | Service health check |
| `/docs` | GET | Interactive API documentation |

## Troubleshooting

### Queue is growing but not syncing?
```bash
curl http://localhost:8001/api/queue/status
```
Check `last_error` field to see what's failing. Most common: DNS resolution of `backend:8000` from inside Docker.

### Need to manually trigger sync?
```bash
curl -X POST http://localhost:8001/api/queue/sync
```

### Check service logs?
```bash
docker logs hacknu26-backup-queue-1 -f
```

## Next Steps

1. ✅ **Backup Service:** Deployed and tested
2. 📋 **Dispatcher Service:** Admin hub for viewing all locomotives (Phase 2)
3. 📋 **Kafka Integration:** Multi-consumer event streaming (Phase 3, optional)

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full roadmap.
