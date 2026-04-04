# SQLAlchemy ORM model for alerts.
#
# class AlertRecord(Base):
#   __tablename__ = "alerts"
#
#   id: UUID, primary key
#   locomotive_id: String(64), indexed
#   code: String(64)               (AlertCode, e.g. "ENG_OVERHEAT")
#   severity: String(16)           ("info" | "warning" | "critical")
#   message: Text
#   fired_at: DateTime(timezone=True), not null
#   resolved_at: DateTime(timezone=True), nullable
#   acknowledged_at: DateTime(timezone=True), nullable
#   acknowledged_by: String(256), nullable  (user sub from JWT)
#
# Indexes:
#   (locomotive_id, fired_at DESC)
#   (locomotive_id, code, resolved_at) — to find currently active alerts
