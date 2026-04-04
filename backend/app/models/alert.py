from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base


def _utcnow() -> datetime:
	return datetime.now(timezone.utc)


class LocomotiveWarning(Base):
	__tablename__ = "locomotive_warnings"
	__table_args__ = (
		Index("ix_locomotive_warnings_loco_active", "locomotive_id", "active"),
		Index("ix_locomotive_warnings_loco_rule", "locomotive_id", "rule_id"),
	)

	warning_id: Mapped[str] = mapped_column(String(128), primary_key=True)
	locomotive_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
	rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
	severity: Mapped[str] = mapped_column(String(16), nullable=False)
	title: Mapped[str] = mapped_column(String(128), nullable=False)
	message: Mapped[str] = mapped_column(Text, nullable=False)
	recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
	active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
	first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
	last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
