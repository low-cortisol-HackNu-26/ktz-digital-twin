# SQLAlchemy ORM model for the card registry.
#
# class CardRecord(Base):
#   __tablename__ = "cards"
#
#   id: UUID, primary key
#   uid_hash: String(64), unique, not null   (SHA-256 of raw card UID — never store raw UID)
#   operator_name: String(256), not null
#   role: String(32), not null               ('Machinist' | 'Dispatcher' | 'Admin')
#   assigned_locomotive_id: String(64), nullable  (null = Dispatcher/Admin, not assigned to one loco)
#   is_active: Boolean, default True         (set False to deactivate lost/stolen card)
#   created_at: DateTime(timezone=True)
#   last_used_at: DateTime(timezone=True), nullable
#
# Note: cards are seeded via infra/postgres/seed_cards.sql or an Admin API endpoint.
# Raw card UIDs are never persisted — only their SHA-256 hashes.
