# Railway Telemetry System Architecture

## Current Data Flow

```
Train Simulator (or actual train client)
    ↓
    └─→ POST /api/ingest/telemetry (HTTP)
         ↓
         └─→ Backend App
              ├─→ Store in PostgreSQL
              │   ├─ TelemetryEventRecord (raw events)
              │   ├─ CurrentSnapshot (latest per loco)
              │   ├─ LocomotiveWarning (alerts)
              │   └─ LocomotivePosition (GPS + route)
              │
              ├─→ Redis pub/sub (TELEMETRY_CHANNEL)
              │   ↓
              │   └─→ WebSocket broadcast to connected clients
              │       (frontend dashboard listening on /ws/telemetry/{locomotive_id})
              │
              └─→ In-memory metrics tracking
```

## Current WebSocket Implementation

**Status:** ✅ ACTIVE - Real-time telemetry streaming to dashboard

- **Endpoint:** `/ws/telemetry/{locomotive_id}` (handler.py)
- **Data Flow:** HTTP POST → Redis publish → WebSocket broadcast
- **Use Case:** Real-time dashboard updates, alerts, live monitoring
- **Limitation:** No offline queueing if client disconnects

---

## Proposed Architecture: Backup & Dispatcher System

### Phase 1: Backup Microservice (Data Persistence on Client Disconnect)

```
Train Client (offline/unreliable network)
    ├─→ POST /api/ingest/telemetry (if online)
    │    └─→ Backend App → DB → Redis → WebSocket
    │
    └─→ Local SQLite/LevelDB Queue (if offline)
         └─→ Retry queue with exponential backoff
         └─→ Sync when network recovers
              └─→ POST /api/ingest/telemetry/batch
```

**Microservice: `backup-queue-service`**
- **Language:** Python (FastAPI)
- **Port:** 8001
- **Responsibilities:**
  - Provide local storage API for train clients
  - Queue telemetry when backend unreachable
  - Retry with exponential backoff when backend recovers
  - Optional: Send to Kafka for dispatcher consumption

---

### Phase 2: Dispatcher Microservice (Admin Hub)

```
┌─────────────────────────────────────────────────────────┐
│                  Dispatcher Microservice                 │
│                                                          │
│  Admin Interface (Web Dashboard)                        │
│  ├─ View all locomotives                               │
│  ├─ View all routes with live positions                │
│  ├─ Historical telemetry analysis                       │
│  ├─ Alert management & rules                           │
│  └─ System health & metrics                            │
│                                                          │
│  APIs:                                                   │
│  ├─ GET /api/dispatcher/fleet (all locos + positions)  │
│  ├─ GET /api/dispatcher/routes (all routes)            │
│  ├─ GET /api/dispatcher/alerts (active warnings)       │
│  ├─ POST /api/dispatcher/alerts/rules (manage rules)   │
│  ├─ GET /api/dispatcher/metrics (system health)        │
│  └─ WS /ws/dispatcher/metrics (real-time stats)        │
│                                                          │
└─────────────────────────────────────────────────────────┘
     ↑                                  ↑
     │                                  │
     └──────────────────┬───────────────┘
                        │
        Consumes from (via Kafka)
        ┌──────────────┴──────────────┐
        │                             │
    Backend App                  Backup Service
    (publishes events)           (publishes queued)
```

---

### Phase 3: Kafka Message Queue

**Kafka Topics:**

1. **`telemetry.events`** (Main event stream)
   - Source: Backend (every POST /api/ingest/telemetry)
   - Partition key: `locomotive_id` (ensures ordering per loco)
   - Consumers:
     - Dispatcher (subscribe + store in DispatcherDB)
     - Analytics (time-series analysis)
     - Alerting engine

2. **`telemetry.backlog`** (Offline queue events)
   - Source: Backup Service (when connectivity restored)
   - Partition key: `locomotive_id`
   - Consumer: Dispatcher (treat same as `telemetry.events`)

3. **`alerts.generated`** (Warning/fault alerts)
   - Source: Backend (LocomotiveWarning creation)
   - Partition key: `locomotive_id`
   - Consumer: Dispatcher (for alert dashboard + rules engine)

4. **`system.metrics`** (Health & performance)
   - Source: Backend (once per minute)
   - Consumer: Dispatcher dashboard

---

## Service Topology

```
┌──────────────────────────────────────────────────────────────┐
│                      Docker Compose Stack                     │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  postgres (main DB) ┬─── backend (8000)                      │
│                     │    ├─ REST endpoints (/api/...)        │
│                     │    ├─ WebSocket (/ws/telemetry/...)    │
│                     │    └─ Redis pub/sub consumer           │
│                     │                                         │
│  redis ─────────────┤                                         │
│                     │                                         │
│                     ├─── kafka (9092)                        │
│                     │    ├─ Topic: telemetry.events          │
│                     │    ├─ Topic: telemetry.backlog         │
│                     │    └─ Topic: alerts.generated          │
│                     │                                         │
│                     ├─── backup-queue-service (8001)         │
│                     │    ├─ Local SQLite queue               │
│                     │    ├─ Retry mechanism                  │
│                     │    └─ Kafka producer                   │
│                     │                                         │
│  dispatcher-db ─────┴─── dispatcher-service (8002)           │
│  (PostgreSQL)           ├─ Admin APIs                        │
│                         ├─ Kafka consumer                    │
│                         ├─ WebSocket /ws/dispatcher/...      │
│                         └─ Alert rules engine                │
│                                                               │
│  simulator ────→ backend (sends telemetry)                   │
│  nginx ────→ dispatcher-service (admin UI)                   │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## Implementation Priority

### ✅ Already Done
- Backend telemetry ingestion (/api/ingest/telemetry)
- WebSocket real-time streaming
- PostgreSQL data persistence
- Redis pub/sub event distribution
- Simulator generating telemetry

### 🔄 Phase 1: Backup Service (Offline Queueing)
**Why first?** Solves immediate pain point of losing data when client disconnects

**Tasks:**
1. Create `backup-queue-service/` microservice
2. SQLite queue for buffering telemetry when backend unreachable
3. Health check + retry logic with exponential backoff
4. Batch upload endpoint: `POST /api/ingest/telemetry/batch`
5. Kafka producer integration (optional for phase 1)
6. Docker service in compose file

**Deliverable:** Train clients can queue telemetry locally, auto-sync when online

---

### 🔄 Phase 2: Dispatcher Microservice (Admin Hub)
**Why second?** Needs stable data source (phases 1 + 0)

**Tasks:**
1. Create `dispatcher-service/` (FastAPI)
2. Separate PostgreSQL database (`dispatcher_db`)
3. Kafka consumer → store events in dispatcher DB
4. Admin APIs:
   - Fleet view (all locos + live position + last telemetry)
   - Routes with locomotive markers
   - Alert dashboard
   - Historical analysis
5. WebSocket for real-time updates
6. Simple admin dashboard (Next.js or React)

**Deliverable:** Admin can monitor all assets, see alerts, analyze routes

---

### 🔄 Phase 3: Kafka Integration (Optional, for scalability)
**Why last?** Can work without it initially, adds value when system scales

**Use Case:**
- Decouple services: backend doesn't wait for dispatcher
- Enable multiple consumers (analytics, alerting, archival)
- Replay events for debugging
- Stream processing (anomaly detection)

**Decision:** Start with Redis pub/sub for simplicity, migrate to Kafka when:
- Multiple dispatcher instances needed
- Long-term event replay required
- Stream processing pipeline needed

---

## Backup Service Details

### Data Model
```python
# SQLite schema
CREATE TABLE telemetry_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    locomotive_id TEXT NOT NULL,
    event_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP,
    retry_count INTEGER DEFAULT 0,
    error_message TEXT
);

CREATE INDEX idx_locomotive_synced ON telemetry_queue(locomotive_id, synced_at);
```

### Sync Algorithm
```
1. On startup: Check for unsync'd events
2. Every 30s: Try to POST unsync'd events to backend in batches
3. Exponential backoff: 1s → 5s → 30s → 5m → 30m
4. Mark successful events as synced
5. On backend offline: Keep queueing locally
6. On backend online: Resume sync from queue
```

### APIs
```
POST /queue/telemetry
- Body: { "locomotive_id": "KZ8A-0001", "event": {...} }
- Response: { "queued": true, "backend_status": "unreachable" }

GET /queue/status
- Response: { "queued_count": 150, "backend_reachable": false, "last_sync": "..." }

POST /queue/sync (manual trigger)
- Response: { "synced": 45, "remaining": 105 }
```

---

## Dispatcher Service Details

### Database Schema
```python
# dispatcher_db PostgreSQL
CREATE TABLE dispatcher_events (
    id BIGSERIAL PRIMARY KEY,
    locomotive_id TEXT NOT NULL,
    event_data JSONB NOT NULL,
    received_at TIMESTAMP NOT NULL,
    created_by TEXT  -- "backend" | "backup-service"
);

CREATE INDEX idx_loco_time ON dispatcher_events(locomotive_id, received_at DESC);

CREATE TABLE dispatcher_alerts (
    id UUID PRIMARY KEY,
    locomotive_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    severity TEXT,  -- "info" | "warning" | "critical"
    message TEXT,
    first_seen_at TIMESTAMP,
    last_seen_at TIMESTAMP,
    resolved_at TIMESTAMP
);
```

### Admin APIs
```
GET /api/dispatcher/fleet
- Response: [{ "locomotive_id": "KZ8A-0001", "current_speed": 100, "position": {...}, "last_telemetry": "..." }]

GET /api/dispatcher/fleet/{locomotive_id}/history
- Query: ?from=2026-04-05T10:00Z&to=2026-04-05T12:00Z
- Response: [{ "timestamp": "...", "speed": 100, "gps_lat": ..., ... }]

GET /api/dispatcher/alerts
- Response: [{ "locomotive_id": "KZ8A-0002", "severity": "critical", "message": "..." }]

POST /api/dispatcher/alerts/rules
- Create/update alert rules (speed > 120, temp > 100, etc.)

WS /ws/dispatcher/metrics
- Real-time: { "total_events": 15000, "active_locos": 3, "alerts": 2 }
```

---

## Next Steps

1. **Create backup-queue-service** (if you want offline resilience)
2. **Integrate Kafka** (if you want scalable multi-consumer architecture)
3. **Create dispatcher-service** (if you want admin hub + historical analysis)

Currently your system works great for **real-time monitoring** via WebSocket. The backup + dispatcher layers are for **resilience** and **admin visibility**.

Would you like me to start implementing any of these phases?
