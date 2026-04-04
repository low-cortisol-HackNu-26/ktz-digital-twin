# SQLAlchemy ORM model for telemetry storage.
#
# class TelemetryRecord(Base):
#   __tablename__ = "telemetry"
#   TimescaleDB hypertable — partition by timestamp
#
#   id: BigInteger, primary key (auto)
#   locomotive_id: String(64), indexed
#   timestamp: DateTime(timezone=True), not null  ← partition key
#   speed: Float
#   throttle: Float
#   fuel_level: Float
#   fuel_consumption_rate: Float
#   engine_temp: Float
#   oil_pressure: Float
#   brake_pressure: Float
#   voltage: Float
#   current: Float
#   latitude: Float (nullable)
#   longitude: Float (nullable)
#   health_score: Float
#   health_grade: String(1)
#   raw_json: JSONB  (stores full packet for fields not in schema)
#
# Indexes:
#   (locomotive_id, timestamp DESC) — for history queries
#
# Note: TimescaleDB retention policy (72h) configured in migrations/001_initial.sql
