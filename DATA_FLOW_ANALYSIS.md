# Dispatcher Data Flow Analysis

## Overview
The **Dispatcher Service** is the admin hub that displays fleet status, warnings, and allows user management. Here's where it gets its data:

---

## 1. **Telemetry Data Flow** (Real-time Position, Speed, etc.)

```
Simulator / Locomotive
       ↓
Backup Queue Service
       ↓
Dispatcher Ingest Endpoint (/api/ingest/telemetry)
       ↓
Dispatcher Database
       ├── locomotive_telemetry (all events)
       ├── locomotive_position (latest position per loco)
       └── locomotive (locomotive registry)
```

### Key Components:

**Source:** `Backup Queue Service` (port 8001)
- **Location:** `/backup-queue/app/sync_manager.py`
- **What it does:** 
  - Queues telemetry events from locomotives
  - Periodically syncs pending items to the dispatcher's ingest endpoint
  - Uses exponential backoff retry (1 sec to 30 min)
  - **Target URL:** `http://dispatcher:8002/api/ingest/telemetry`

**Entry Point:** `Dispatcher /api/ingest/telemetry` 
- **Location:** `/dispatcher/app/routes/ingest.py`
- **Lines 40-100:**
  - Accepts list of events (or single event)
  - Parses: `locomotive_id`, `timestamp`, `speed_kph`, `gps_lat`, `gps_lng`, `route_segment`
  - Stores in `LocomotiveTelemetry` table (all events)
  - Updates `LocomotivePosition` table (latest position per locomotive)
  - Creates/verifies `Locomotive` entry if not exists

**Output Used By:**
- `/api/dispatcher/fleet` — shows current position, speed, online status
- Dashboard metrics — speed averages, route tracking

---

## 2. **Warning Sync** (Active/Historical Alerts)

```
Backend Service (port 8000)
       ↓
Dispatcher Background Task (/api/warnings/all endpoint)
       ↓
sync_warnings_from_backend()
       ↓
Dispatcher Database (locomotive_warning table)
```

### Key Components:

**Source:** `Backend Service` (port 8000)
- **API Endpoint:** `/api/warnings/all`
- **Security:** Requires `X-Sync-Secret` header

**Sync Task:** `start_background_sync()`
- **Location:** `/dispatcher/app/tasks/sync.py`
- **Lines 40-100:**
  - Runs in background during startup
  - Periodically fetches warnings from backend
  - Creates or updates `LocomotiveWarning` records locally
  - Syncs fields: `warning_id`, `severity`, `title`, `message`, `active`, `expires_at`

**Output Used By:**
- `/api/dispatcher/fleet` — `active_warnings_count` per locomotive
- `/api/warnings/active` — shows all active warnings
- `/api/warnings/locomotive/{locomotive_id}` — warnings for specific loco

---

## 3. **Fleet Status Endpoint** (`GET /api/dispatcher/fleet`)

**Location:** `/dispatcher/app/routes/dashboard.py:33-90`

**Data Assembly:**
```python
# 1. Get all locomotives from dispatcher.locomotive table
locomotives = await db.execute(select(Locomotive))

# 2. Get latest positions from dispatcher.locomotive_position table
positions_map = {p.locomotive_id: p for p in positions}

# 3. Count active warnings per locomotive
warning_counts = {locomotive_id: count}

# 4. Check if "online" (position updated in last 5 minutes)
is_online = (now - position.updated_at).total_seconds() < 300

# 5. Build response with aggregated data
```

**Response contains:**
- `locomotive_id`
- `lat`, `lng` (from locomotive_position)
- `speed_kph` (from locomotive_position)
- `is_online` (time-based)
- `active_warnings_count` (from locomotive_warning)
- `last_updated` (timestamp of last position update)

---

## 4. **Data Sources Summary**

| Data Type | Source | Entry Point | Storage | Real-time? |
|-----------|--------|------------|---------|-----------|
| **Position/Speed** | Backup Queue | `/api/ingest/telemetry` | `locomotive_position` | ✅ Yes (seconds) |
| **All Events** | Backup Queue | `/api/ingest/telemetry` | `locomotive_telemetry` | ✅ Yes |
| **Warnings** | Backend Service | Background sync task | `locomotive_warning` | ⚠️ Periodic (~every sync interval) |
| **Users** | Auth/Registration | `/api/auth/register` | `users` table | Immediate |
| **Routes** | Backend | Background sync? | `routes` table | Depends on backend |
| **Locomotive Registry** | Auto-created | `/api/ingest/telemetry` | `locomotive` table | Auto-created on first event |

---

## 5. **Key Configuration**

**Backup Queue → Dispatcher Sync:**
```python
# backup-queue/app/sync_manager.py:26
SyncManager(backend_url="http://dispatcher:8002", check_interval=30)
# Retries every 30 seconds with exponential backoff
```

**Dispatcher ← Backend Sync:**
```python
# dispatcher/app/tasks/sync.py:31
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
SYNC_SECRET = os.getenv("SYNC_SECRET", "")
# Syncs warnings from backend in background task
```

---

## 6. **Data Latency**

| Data Type | Latency |
|-----------|---------|
| Telemetry (pos/speed) | ~30 sec (sync interval) or immediate if available |
| Warnings | ~30-60 sec (depends on backend sync interval) |
| User changes | Immediate |
| Route info | Depends on backend |

---

## 7. **Critical Path for Fleet Status**

1. **Locomotive sends telemetry** → Backup Queue (buffered)
2. **Backup Queue syncs** every 30 sec → `POST /api/ingest/telemetry`
3. **Dispatcher receives** → Stores in `locomotive_telemetry` & upserts `locomotive_position`
4. **Admin queries** `GET /api/dispatcher/fleet`
5. **Response built** by joining:
   - `Locomotive` table
   - `LocomotivePosition` table (latest)
   - `LocomotiveWarning` table (active)

---

## 8. **Synchronization Flow Diagram**

```
┌─────────────────────────────────────────────────────────┐
│                   DISPATCHER SERVICE                    │
│                    (Port 8002)                          │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Database Tables:                                       │
│  ├─ locomotive (registry)                              │
│  ├─ locomotive_position (latest position/speed)        │
│  ├─ locomotive_telemetry (all events)                  │
│  ├─ locomotive_warning (active alerts)                 │
│  └─ users (auth)                                       │
│                                                          │
│  Ingest Endpoints:                                      │
│  ├─ POST /api/ingest/telemetry ← Backup Queue         │
│  └─ Background sync ← Backend /api/warnings/all        │
│                                                          │
└─────────────────────────────────────────────────────────┘
         ↑                                    ↑
         │                                    │
    ┌────┴─────────────┐            ┌────────┴──────┐
    │  BACKUP QUEUE    │            │  BACKEND      │
    │  (Port 8001)     │            │  (Port 8000)  │
    │                  │            │               │
    │ sync_manager.py  │            │ Warning sync  │
    │ ↓                │            │               │
    │ Every 30 sec     │            │ On-demand or  │
    │ POST telemetry   │            │ periodic      │
    └────┬─────────────┘            └───────────────┘
         ↑
         │
    ┌────┴──────────────────┐
    │  LOCOMOTIVES/SIMULATOR │
    │  (Sends telemetry)     │
    └───────────────────────┘
```

---

## 9. **What Gets Queued in Backup Queue vs What's Real-time**

### Backup Queue Service (`/backup-queue`):
- **Telemetry Queue**: Stores locomotive telemetry events (position, speed, temp, etc.)
  - Syncs to **Dispatcher** periodically (every 30 sec)
  - Also syncs to **Backend** if available
  - Purpose: Handle offline periods, ensure no data loss

### Dispatcher:
- **Receives** synced telemetry from Backup Queue
- **Stores locally** in `locomotive_position` and `locomotive_telemetry`
- **Syncs warnings** from Backend in background task
- **Serves** real-time fleet status API

### Backend:
- **Receives** telemetry from Backup Queue or directly
- **Generates warnings** based on telemetry thresholds
- **Stores** in `warnings` table
- **Dispatcher syncs** these warnings periodically

---

## Summary

**The Dispatcher gets data from:**

1. **Primary Source - Backup Queue Service** (Real-time telemetry)
   - Locomotives send telemetry → Backup Queue stores it → Every 30 sec syncs to Dispatcher
   - Entry: `POST /api/ingest/telemetry`

2. **Secondary Source - Backend Service** (Warnings)
   - Backend generates warnings from telemetry
   - Dispatcher background task periodically syncs: `GET /api/warnings/all`

3. **Tertiary Source - Direct Input** (User management)
   - Users registered via `/api/auth/register`
   - Stored directly in dispatcher database

**Fleet Status Response** is assembled by querying Dispatcher's local database tables and joining current data.
