# KTZ Digital Twin — Locomotive Fleet Monitoring Platform

A real-time digital twin platform for KTZ (Kazakhstan Temir Zholy) locomotive fleet operations. The system ingests high-frequency telemetry from rolling stock, evaluates health indices across five physical subsystems, generates automated warnings, and provides live dashboards for both drivers and dispatchers.

---

## Table of Contents

- [Ключевые возможности и API](#ключевые-возможности-и-api)
- [Architecture Overview](#architecture-overview)
- [Service Descriptions](#service-descriptions)
- [Data Flow](#data-flow)
- [Technology Stack](#technology-stack)
- [Security Model](#security-model)
- [Health Index](#health-index)
- [Warning System](#warning-system)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [High-Load Testing](#high-load-testing)
- [API Reference](#api-reference)

---

## Ключевые возможности и API

### Ключевые возможности

**Мониторинг в реальном времени**
Телеметрия поступает с частотой 5 Гц и мгновенно отображается через WebSocket. Задержка от симулятора до экрана — менее 100 мс.

**Индекс здоровья (0–100)**
Взвешенная оценка по пяти подсистемам: электрика (0.25), тормоза (0.25), давление (0.22), напряжение (0.17), ток (0.11). При деградации любой из них индекс падает пропорционально отклонению от допустимых порогов.

**Автоматические предупреждения**
Перегрев, низкое давление, провал напряжения, вибрация, превышение скорости — каждое нарушение порога создаёт запись `LocomotiveWarning` и появляется у машиниста в реальном времени.

**Диспетчерское управление**
Диспетчер выдаёт предупреждения на конкретный локомотив или на весь сегмент маршрута через отдельный UI и API.

**Надёжность**
Backup Queue буферизует пакеты при недоступности бэкенда и повторяет отправку с экспоненциальной задержкой — данные не теряются.

**Безопасность**
JWT с ротацией refresh-токенов, PBKDF2-SHA256 (390 000 итераций), разграничение ролей, межсервисный `X-Sync-Secret`.

---

### API Documentation

Все эндпоинты Backend доступны на `:8000/api/...`, Dispatcher — на `:8002/api/...`. Интерактивная документация: `/docs` на каждом сервисе.

#### Аутентификация (Backend & Dispatcher — идентичный интерфейс)

| Метод | Путь | Описание |
|---|---|---|
| `POST` | `/api/auth/register` | Регистрация пользователя. Первый пользователь — Admin без токена. Последующие — только Admin с токеном. |
| `POST` | `/api/auth/card` | Вход по ID и паролю. Возвращает `access_token` (8 ч) + `refresh_token` (7 д). |
| `POST` | `/api/auth/refresh` | Обновление пары токенов. Refresh-токен ротируется при каждом использовании. |
| `POST` | `/api/auth/logout` | Отзыв сессии. Немедленно инвалидирует refresh-токен. |
| `GET` | `/api/auth/me` | Информация о текущем пользователе. Требует `Authorization: Bearer <token>`. |
| `POST` | `/api/auth/token` | OAuth2 Password Flow для Swagger UI (только Admin). |

Пример входа:

```bash
curl -X POST http://localhost:8000/api/auth/card \
  -H "Content-Type: application/json" \
  -d '{"uid": "admin", "password": "secret"}'
```

Ответ:

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "session_id": "uuid",
  "driver": { "id": "...", "name": "Admin", "role": "Admin" }
}
```

#### Телеметрия (Backend `:8000`)

| Метод | Путь | Auth | Описание |
|---|---|---|---|
| `POST` | `/api/ingest/telemetry` | Нет | Приём пакета (или батча) телеметрии. Принимает одиночный объект или массив. |
| `GET` | `/api/locomotives` | Нет | Список всех зарегистрированных локомотивов. |
| `GET` | `/api/locomotives/{id}/current` | Нет | Текущий снимок: все метрики + активные предупреждения + health index. |
| `GET` | `/api/locomotives/{id}/latest-metrics` | Нет | Последние метрики в плоском формате. |
| `GET` | `/api/locomotives/{id}/history` | Нет | История телеметрии за период. Query: `from`, `to` (ISO 8601), `limit` (макс. 10 000). |
| `GET` | `/api/locomotives/{id}/warnings` | Нет | История предупреждений локомотива. |
| `GET` | `/api/locomotives/{id}/replay` | Нет | Воспроизведение телеметрии за период с привязкой предупреждений к временным меткам. |
| `GET` | `/api/locomotives/{id}/replay/frames` | Нет | Только массив кадров без метаданных. |
| `GET` | `/api/locomotives/{id}/ingestion-stats` | Нет | Статистика приёма пакетов по локомотиву. |
| `GET` | `/api/ingestion/stats` | Нет | Агрегированная статистика по всем локомотивам. |
| `GET` | `/api/system/metrics` | Нет | Системные метрики: пакеты/с, задержка записи в БД, счётчики ошибок. |

Минимальный пакет телеметрии:

```json
{
  "timestamp": "2026-04-05T10:00:00Z",
  "locomotive_id": "KZ8A-0001",
  "traction_type": "electric",
  "speed_kph": 85.3,
  "traction_mode": "traction",
  "pantograph_up": true
}
```

Валидационные ограничения полей:

- Давление (`brake_pipe_pressure_bar`, `pneumatic_pressure_bar`): 0–16 bar
- Температура (`traction_motor_temp_c`, `brakes_temperature_c` и др.): -60–220 °C
- Напряжение (`catenary_voltage_kv`): 0–35 kV
- Ток (`traction_current_a`): 0–5 000 A
- Качество сигнала (`signal_quality`, `data_quality`): 0.0–1.0

#### WebSocket (Backend `:8000`)

```
ws://localhost:8000/ws/telemetry/{locomotive_id}
```

Соединение подписывается на Redis-канал `telemetry:{locomotive_id}`. При каждом новом пакете сервер отправляет полный JSON-снимок локомотива (те же данные, что и `/current`). При подключении сразу отдаётся последний сохранённый снимок. Клиент может отправить `"ping"` — сервер ответит `"pong"`.

#### Карта (Backend `:8000`)

| Метод | Путь | Auth | Описание |
|---|---|---|---|
| `GET` | `/api/map/routes` | Bearer | Все маршруты в формате GeoJSON FeatureCollection. |
| `GET` | `/api/map/routes/{route_id}` | Bearer | Один маршрут по ID. |
| `GET` | `/api/map/fleet` | Bearer | Текущие позиции всех активных локомотивов. |
| `POST` | `/api/map/position` | Bearer | Ручное обновление GPS-позиции локомотива. |

#### Диспетчерские предупреждения (Backend `:8000`)

| Метод | Путь | Auth | Описание |
|---|---|---|---|
| `POST` | `/api/dispatcher/warnings` | Нет | Создать ручное предупреждение на локомотив или сегмент маршрута. |
| `GET` | `/api/warnings/all` | `X-Sync-Secret` | Все активные предупреждения флота (для синхронизации диспетчера). |

Тело запроса `POST /api/dispatcher/warnings`:

```json
{
  "target_type": "locomotive",
  "target_id": "KZ8A-0001",
  "warning_type": "speed_restriction",
  "severity": "warning",
  "title": "Ограничение скорости",
  "message": "Плохое состояние пути на км 142",
  "recommended_action": "Снизить скорость до 40 км/ч",
  "allowed_speed_kph_override": 40.0,
  "duration_seconds": 1800,
  "source": "dispatcher",
  "created_by": "disp-001"
}
```

`target_type` — `"locomotive"` или `"route_segment"`. При `"route_segment"` предупреждение применяется ко всем локомотивам на этом сегменте.

#### Диспетчер — Флот и маршруты (Dispatcher `:8002`)

| Метод | Путь | Auth | Описание |
|---|---|---|---|
| `GET` | `/api/fleet` | Bearer | Состояние флота: все локомотивы, скорость, маршрут, активные предупреждения. |
| `GET` | `/api/metrics` | Bearer | Агрегированные метрики дашборда. |
| `GET` | `/api/routes` | Bearer | Список всех маршрутов. |
| `GET` | `/api/map/routes` | Bearer | GeoJSON маршруты для карты диспетчера. |
| `GET` | `/api/locomotive/{id}` | Bearer | Детали конкретного локомотива. |
| `GET` | `/api/locomotives/{id}/report/15min` | Bearer | Скачать PDF-отчёт за последние 15 минут. |

#### Диспетчер — Управление предупреждениями (Dispatcher `:8002`)

| Метод | Путь | Auth | Описание |
|---|---|---|---|
| `POST` | `/api/warnings` | Bearer | Создать предупреждение через диспетчерский UI. |
| `GET` | `/api/warnings` | Bearer | Все активные предупреждения по флоту. |
| `GET` | `/api/warnings/locomotive/{id}` | Bearer | Активные предупреждения конкретного локомотива. |
| `GET` | `/api/warnings/history` | Bearer | История предупреждений. |
| `PUT` | `/api/warnings/{warning_id}/deactivate` | Bearer | Деактивировать предупреждение досрочно. |
| `PUT` | `/api/warnings/{warning_id}/renew` | Bearer | Продлить срок действия предупреждения. |

#### Диспетчер — Управление пользователями (Dispatcher `:8002`)

| Метод | Путь | Auth | Описание |
|---|---|---|---|
| `GET` | `/api/users` | Bearer (Admin) | Список всех операторов. |
| `GET` | `/api/users/{id}` | Bearer (Admin) | Детали пользователя. |
| `PUT` | `/api/users/{id}/role` | Bearer (Admin) | Изменить роль пользователя. |
| `PUT` | `/api/users/{id}/locomotive` | Bearer (Admin) | Назначить локомотив оператору. |
| `DELETE` | `/api/users/{id}` | Bearer (Admin) | Деактивировать пользователя (мягкое удаление). |

При создании или изменении пользователя через диспетчер изменения автоматически синхронизируются в бэкенд через Backup Queue.

#### Внутренняя синхронизация (Backend `:8000`, только для сервисов)

| Метод | Путь | Auth | Описание |
|---|---|---|---|
| `POST` | `/api/sync/users` | `X-Sync-Secret` | Синхронизация пользователя из диспетчера в бэкенд. |
| `POST` | `/api/sync/routes` | `X-Sync-Secret` | Синхронизация маршрутов. |

---

## Architecture Overview

```
                         ┌─────────────────────────────┐
                         │        Simulator             │
                         │  (KZ8A-0001/0002/0003)       │
                         └───────────┬─────────────────┘
                                     │ POST /api/ingest/telemetry
                                     ▼
┌───────────────┐   sync/store   ┌──────────────────┐   Redis   ┌────────────────┐
│  Backup Queue │◄───and─────────│   Backend :8000   │──pub/sub─►│  WebSocket WS  │
│   :8001       │   forward      │   (FastAPI)        │           │  /ws/telemetry │
└───────────────┘                └────────┬─────────┘           └────────┬───────┘
        │                                 │                               │
        │ forward telemetry               │ PostgreSQL                    │
        ▼                                 ▼ (TimescaleDB)                 │
┌───────────────┐                ┌──────────────────┐                    ▼
│  Dispatcher   │                │   postgres:5433   │          ┌─────────────────┐
│   :8002       │◄───sync─users──│                  │          │  Driver App     │
│   (FastAPI)   │                └──────────────────┘          │  :3000 (Next.js)│
└───────┬───────┘                                              └─────────────────┘
        │ PostgreSQL
        ▼ (TimescaleDB)
┌──────────────────┐             ┌─────────────────────┐
│ postgres-disp    │             │  Dispatcher UI      │
│ :5434            │             │  :3001 (Next.js)    │
└──────────────────┘             └─────────────────────┘
```

---

## Service Descriptions

### Backend (`backend/`, port 8000)

The primary data service. Responsibilities:

- **Telemetry ingestion** — validates, normalises, and persists every telemetry packet to TimescaleDB
- **Warning engine** — evaluates threshold rules on each ingested event; creates, updates, and expires `LocomotiveWarning` records
- **Health index** — computes a 0–100 composite score per locomotive across five physical domains
- **Real-time fan-out** — publishes enriched snapshots to Redis after each ingestion; WebSocket endpoint streams these to connected clients
- **Route matching** — snaps GPS coordinates to the nearest railway route using Haversine geometry
- **Authentication** — issues JWT access tokens (8 h) and refresh tokens (7 d) with session-level revocation

### Dispatcher (`dispatcher/`, port 8002)

The fleet management service for railway control-centre operators. Responsibilities:

- **Manual warnings** — operators can issue targeted warnings to a specific locomotive or all locomotives on a route segment
- **Fleet dashboard** — aggregates current snapshot data across the entire fleet
- **User management** — creates and manages operator accounts; syncs users back to the backend via the backup queue
- **Report generation** — produces 15-minute PDF reports per locomotive
- **Telemetry mirror** — receives the same telemetry stream from the backup queue for offline resilience

### Backup Queue (`backup-queue/`, port 8001)

A lightweight SQLite-backed store-and-forward proxy. Responsibilities:

- Buffers outbound telemetry and user-sync messages when the backend or dispatcher is temporarily unavailable
- Retries with exponential backoff (capped at 30 s)
- Prevents data loss during rolling restarts or transient network failures

### Simulator (`simulator/`)

A physics-based locomotive simulator for development and load testing. Each simulated locomotive runs a finite state machine (RUNNING → TERMINUS_WAIT → RUNNING) along a GPS route, applying:

- Realistic kinematics (traction, coasting, braking)
- Live metric dynamics (temperature, pressure, voltage)
- Random fault injection (overspeed, high temperature, voltage sag, vibration, etc.)

### Frontend (`frontend/`, port 3000)

Next.js 15 / React 19 driver-facing dashboard. Features:

- Live telemetry panels with threshold-based colour coding
- Leaflet map with locomotive position markers and route overlays
- Warning cards grouped by subsystem
- Historical charts (Recharts)
- Health index gauge per subsystem

### Dispatcher UI (`dispatcher-ui/`, port 3001)

Next.js 15 / React 19 dispatcher-facing dashboard. Features:

- Fleet overview map
- Manual warning creation form (target locomotive or route segment)
- Warning management table (deactivate, renew)
- PDF report download

---

## Data Flow

### Real-Time Telemetry (per tick, default 5 Hz)

1. Simulator sends `POST /api/ingest/telemetry` to Backend with a full `TelemetryEvent` JSON payload.
2. Backend validates the payload (Pydantic v2 field validators with physical range checks).
3. Backend normalises metric aliases (`engine_temperature_c` ↔ `traction_motor_temp_c`, etc.).
4. Backend snaps GPS coordinates to the nearest route; computes ETA and route progress.
5. Backend evaluates warning rules; upserts `LocomotiveWarning` rows; expires stale warnings.
6. Backend computes the health index.
7. Backend writes the event to the `telemetry_events` hypertable (TimescaleDB).
8. Backend writes/updates the `current_snapshots` row for this locomotive.
9. Backend publishes the enriched snapshot to Redis channel `telemetry:{locomotive_id}`.
10. WebSocket server fans the Redis message out to all subscribed clients.
11. Backend queues the snapshot to Backup Queue (`POST /api/queue`) for dispatcher mirroring.

### Manual Warning Flow

1. Dispatcher operator submits a warning form in the Dispatcher UI.
2. Dispatcher UI calls `POST /api/dispatcher/warnings` on Dispatcher service.
3. Dispatcher creates `LocomotiveWarning` rows in its own database.
4. Dispatcher pushes the warning to Backend via the backup queue (store-and-forward).
5. Backend updates its snapshot and publishes to Redis.
6. Driver App WebSocket receives the updated warnings in real time.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend API | Python 3.12, FastAPI, Uvicorn |
| ORM | SQLAlchemy 2.x async (asyncpg driver) |
| Database | TimescaleDB (PostgreSQL 16 extension) |
| Message bus | Redis 7 pub/sub |
| Auth | HS256 JWT, PBKDF2-SHA256 (390 000 iterations) |
| Frontend | Next.js 15, React 19, Tailwind CSS |
| Charts | Recharts |
| Maps | Leaflet / react-leaflet |
| State | Zustand |
| Simulator | Pure Python asyncio |
| Containerisation | Docker Compose |

---

## Security Model

### Authentication

All protected endpoints require `Authorization: Bearer <access_token>`.

- Access tokens expire after **8 hours**.
- Refresh tokens expire after **7 days** and are rotated on every use (token family protection against theft-and-reuse).
- Sessions are tracked in the `auth_sessions` table; logout immediately revokes the session.
- The first registered user must have the `Admin` role; subsequent registrations require an authenticated Admin.

### Password Storage

Passwords are hashed with PBKDF2-SHA256 at 390 000 iterations using a 16-byte random salt. The stored format is:

```
pbkdf2_sha256$<iterations>$<salt_hex>$<digest_hex>
```

### Internal Service Authentication

Service-to-service calls between Backend and Dispatcher use a shared secret passed in the `X-Sync-Secret` request header. The value is set via the `SYNC_SECRET` environment variable.

### Input Validation

Every telemetry packet is validated by Pydantic v2 with hard physical range constraints:

- Pressures: 0–16 bar
- Temperatures: -60 to 220 °C
- Voltages: 0–35 kV
- Currents: 0–5 000 A

---

## Health Index

The health index is a weighted mean of five physical subsystem scores, each normalised to 0–100.

### Domain Weights

| Domain | Weight | Description |
|---|---|---|
| electricity | 0.25 | Drivetrain temperature + energy/fuel consumption |
| brake | 0.25 | Brake temperature + cylinder effectiveness + vibration |
| pressure | 0.22 | Brake pipe pressure + pneumatic reservoir pressure |
| voltage | 0.17 | Catenary voltage + signal/data link quality |
| current | 0.11 | Traction current draw |

### Scoring Functions

Each metric is mapped to 0–100 with one of two linear functions:

**Low-is-good** (e.g., temperature, current): score = 100 when value is at or below the warning threshold, 0 when value reaches the critical threshold, linear in between.

**High-is-good** (e.g., voltage, pressure, fuel): score = 100 when value is at or above the warning threshold, 0 when value falls to the critical threshold, linear in between.

### Per-Domain Thresholds

**Electricity (weight 0.25)**

- Maximum drive temperature (`traction_motor_temp_c`, `converter_temp_c`, `transformer_temp_c`): warn >= 90 °C, critical >= 115 °C — weight 0.65
- Electric only — `energy_consumption_kwh`: warn >= 7 kWh, critical >= 9 kWh — weight 0.35
- Diesel only — `fuel_level_percent`: warn < 70 %, critical < 40 % — weight 0.35

**Brake (weight 0.25)**

- `brakes_temperature_c`: warn >= 130 °C, critical >= 168 °C — weight 0.55
- `brake_cylinder_pressure_bar` (only evaluated during braking mode): effective >= 1.8 bar = 100, <= 0.3 bar = 0 — weight 0.25
- Maximum of `vibration_gearbox`, `vibration_motor` (g): warn >= 1.5 g, critical >= 3.5 g — weight 0.20

**Pressure (weight 0.22)**

- `brake_pipe_pressure_bar`: warn < 4.2 bar, critical < 3.5 bar — weight 0.55
- `pneumatic_pressure_bar`: warn < 6.5 bar, critical < 5.5 bar — weight 0.45

**Voltage (weight 0.17)**

- Electric only — `catenary_voltage_kv`: warn < 21 kV, critical < 18 kV — weight 0.70
- Signal quality (minimum of `signal_quality` and `data_quality`, 0–1): warn < 0.85, critical < 0.70 — weight 0.30
- Diesel only: signal quality is the sole voltage-domain input

**Current (weight 0.11)**

- `traction_current_a`: warn >= 850 A, critical >= 1 200 A

The implementation is in `backend/app/core/health_index.py`.

---

## Warning System

Warnings are generated automatically on every telemetry ingestion event. Each rule has a severity (`warning` or `critical`) and a unique `rule_id`.

### Automatic Warning Rules

| Rule ID | Trigger condition | Note |
|---|---|---|
| `overspeed` | `speed_kph > allowed_speed_kph` | severity scales with excess |
| `high_temperature` | `traction_motor_temp_c >= 95 °C` (warn) / `>= 110 °C` (critical) | |
| `high_brakes_temperature` | `brakes_temperature_c >= 130 °C` (warn) / `>= 168 °C` (critical) | |
| `low_pneumatic_pressure` | `pneumatic_pressure_bar < 6.0 bar` (warn) / `< 5.0 bar` (critical) | |
| `high_vibration` | `vibration_gearbox >= 2.0 g` (warn) / `>= 3.5 g` (critical) | |
| `voltage_sag` | `catenary_voltage_kv < 20 kV` (warn) / `< 17 kV` (critical) | electric only |
| `low_signal_quality` | `signal_quality < 0.80` (warn) / `< 0.65` (critical) | |
| `bad_track_upcoming` | `upcoming_bad_track` in `active_fault_codes` | |
| `low_fuel` | `fuel_level_percent < 70 %` (warn) / `< 40 %` (critical) | diesel only |

### Warning Lifecycle

1. Created when a threshold is first exceeded.
2. Updated (`last_seen_at`) while the condition persists.
3. Expiry: a warning is automatically deactivated after it has not been re-triggered for `WARNING_TTL_SECONDS` (default 120 s).
4. Manual warnings created by the dispatcher have a fixed `expires_at` set at creation time.

---

## Quick Start

### Prerequisites

- Docker and Docker Compose
- A `.env` file at the repository root

### Minimum `.env`

```env
POSTGRES_DB=ktz
POSTGRES_USER=ktz
POSTGRES_PASSWORD=changeme
JWT_SECRET=change-this-to-a-long-random-string
SYNC_SECRET=change-this-internal-secret
```

### Start all services

```bash
docker compose up --build
```

Services start in dependency order. The simulator begins sending telemetry automatically once the backend is healthy.

| Service | URL |
|---|---|
| Driver App | http://localhost:3000 |
| Dispatcher UI | http://localhost:3001 |
| Backend API docs | http://localhost:8000/docs |
| Dispatcher API docs | http://localhost:8002/docs |

### Register the first user

The first `POST /api/auth/register` must use `"role": "Admin"` and requires no authentication token.

```bash
curl -s -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"uid":"admin","password":"secret","name":"Admin","role":"Admin"}'
```

---

## Environment Variables

### Backend

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | — | asyncpg connection string |
| `REDIS_URL` | `redis://redis:6379/0` | Redis URL |
| `JWT_SECRET` | — | HMAC-SHA256 signing key |
| `SYNC_SECRET` | `internal-sync-secret` | Shared secret for service-to-service calls |
| `BACKUP_QUEUE_URL` | `http://backup-queue:8001` | URL of the backup queue service |
| `KNOWN_LOCOMOTIVES` | — | Comma-separated list of locomotive IDs to pre-create |
| `ALLOWED_ORIGINS` | `["http://localhost:3000"]` | JSON list of CORS-allowed origins |

### Simulator

| Variable | Default | Description |
|---|---|---|
| `INGEST_URL` | — | Backend telemetry ingest endpoint |
| `LOCOS` | `KZ8A-0001,KZ8A-0002,KZ8A-0003` | Comma-separated locomotive IDs to simulate |
| `HZ` | `5` | Ticks per second per locomotive |
| `SCENARIO` | `normal` | Simulation scenario |
| `HIGHLOAD_X10` | `false` | Enable burst load test mode |
| `HIGHLOAD_START_SECONDS` | `10` | Seconds after start before burst begins |
| `HIGHLOAD_DURATION_SECONDS` | `10` | Duration of burst window in seconds |
| `BURST_MULTIPLIER` | `10` | Packet burst multiplier during load test |
| `RANDOM_WARNINGS_ENABLED` | `true` | Enable random fault injection |
| `WARNING_PROBABILITY_PER_TICK` | `0.015` | Probability a new warning fires each tick |
| `WARNING_DURATION_SECONDS` | `6.0` | How long a random warning remains active |
| `WARNING_COOLDOWN_SECONDS` | `4.0` | Minimum gap between new warnings per locomotive |
| `MAX_ACTIVE_WARNINGS_PER_LOCOMOTIVE` | `2` | Maximum concurrent random warnings |

---

## High-Load Testing

The simulator includes a built-in burst mode that replays the current tick state multiple times to simulate elevated ingest rates without requiring additional hardware.

### Via Docker Compose environment variables

```bash
HIGHLOAD_X10=true \
HIGHLOAD_START_SECONDS=10 \
HIGHLOAD_DURATION_SECONDS=30 \
BURST_MULTIPLIER=10 \
docker compose up simulator
```

This sends 10 times the normal packet rate for 30 seconds, beginning 10 seconds after the simulator starts.

### Monitoring ingest throughput under load

```bash
# Overall system metrics (no authentication required)
curl http://localhost:8000/api/system/metrics

# Per-locomotive ingest statistics
curl http://localhost:8000/api/locomotives/KZ8A-0001/ingestion-stats \
  -H "Authorization: Bearer <token>"
```

---

## API Reference

See [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) for the full endpoint reference covering both Backend (:8000) and Dispatcher (:8002) services.

Interactive Swagger UI is available at `/docs` on each service when running locally.
