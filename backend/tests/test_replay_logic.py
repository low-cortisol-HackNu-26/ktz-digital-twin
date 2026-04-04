from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.api.routes.telemetry import _warning_active_at


def test_warning_active_window_logic() -> None:
    start = datetime(2026, 4, 5, 10, 0, 0, tzinfo=UTC)
    cleared = start + timedelta(seconds=6)
    warning = SimpleNamespace(first_seen_at=start, cleared_at=cleared, status="cleared", active=False)

    assert _warning_active_at(warning, start + timedelta(seconds=1)) is True
    assert _warning_active_at(warning, start + timedelta(seconds=5, milliseconds=999)) is True
    assert _warning_active_at(warning, cleared) is False


def test_warning_active_when_no_cleared_at() -> None:
    start = datetime(2026, 4, 5, 10, 0, 0, tzinfo=UTC)
    warning = SimpleNamespace(first_seen_at=start, cleared_at=None, status="active", active=True)

    assert _warning_active_at(warning, start + timedelta(seconds=10)) is True
    assert _warning_active_at(warning, start - timedelta(seconds=1)) is False
