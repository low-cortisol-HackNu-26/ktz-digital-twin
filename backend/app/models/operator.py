import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base


class Operator(Base):
    __tablename__ = "operators"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    employee_id: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True)
    # SHA-256 hex of the raw access token — raw token is never stored
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    # 'Machinist' | 'Dispatcher' | 'Admin'
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    # NULL means the operator is not tied to a single locomotive (Dispatcher / Admin)
    assigned_locomotive_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
