from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_db
from ...core.runtime_state import publish_event
from ...models.alert import LocomotiveWarning
from ...models.telemetry import CurrentSnapshot
from ...schemas.telemetry import ManualWarningCreateRequest, ManualWarningCreateResponse
from .telemetry import _get_active_warnings, _utcnow

router = APIRouter(tags=["dispatcher"])


async def _locomotives_on_segment(db: AsyncSession, route_segment: str) -> list[str]:
	rows = (await db.execute(select(CurrentSnapshot))).scalars().all()
	result: list[str] = []
	for row in rows:
		if str(row.payload.get("route_segment") or "") == route_segment:
			result.append(row.locomotive_id)
	return sorted(set(result))


async def _refresh_snapshot_and_publish(db: AsyncSession, locomotive_id: str) -> None:
	snapshot = (
		await db.execute(
			select(CurrentSnapshot).where(CurrentSnapshot.locomotive_id == locomotive_id)
		)
	).scalar_one_or_none()
	if snapshot is None:
		return

	active_warnings = await _get_active_warnings(db, locomotive_id)
	payload = dict(snapshot.payload)
	payload["active_warnings"] = [item.model_dump(mode="json") for item in active_warnings]
	snapshot.payload = payload
	snapshot.updated_at = _utcnow()
	await publish_event(payload)


@router.post("/dispatcher/warnings", response_model=ManualWarningCreateResponse)
async def create_manual_warning(
	body: ManualWarningCreateRequest,
	db: AsyncSession = Depends(get_db),
) -> ManualWarningCreateResponse:
	now = _utcnow()
	expires_at = now + timedelta(seconds=body.duration_seconds)
	warning_id = f"manual:{body.target_type}:{body.target_id}:{body.warning_type}:{uuid4().hex[:12]}"
	rule_id = f"manual_{body.warning_type}"

	affected_locomotives: list[str] = []
	if body.target_type == "locomotive":
		affected_locomotives = [body.target_id]
	elif body.target_type == "route_segment":
		affected_locomotives = await _locomotives_on_segment(db, body.target_id)
	else:
		raise HTTPException(status_code=422, detail="Unsupported target_type")

	warning = LocomotiveWarning(
		warning_id=warning_id,
		locomotive_id=body.target_id if body.target_type == "locomotive" else f"route_segment:{body.target_id}",
		rule_id=rule_id,
		source=body.source,
		target_type=body.target_type,
		target_id=body.target_id,
		severity=body.severity,
		title=body.title,
		message=body.message,
		recommended_action=body.recommended_action,
		created_by=body.created_by,
		warning_metadata=body.metadata,
		expires_at=expires_at,
		active=True,
		first_seen_at=now,
		last_seen_at=now,
	)
	db.add(warning)

	for locomotive_id in affected_locomotives:
		await _refresh_snapshot_and_publish(db, locomotive_id)

	return ManualWarningCreateResponse(
		warning_id=warning_id,
		target_type=body.target_type,
		target_id=body.target_id,
		affected_locomotive_ids=affected_locomotives,
		expires_at=expires_at,
	)
