from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_db
from ...core.runtime_state import metrics, publish_event
from ...models.telemetry import CurrentSnapshot, IngestionStat, Locomotive, TelemetryEventRecord
from ...schemas.telemetry import (
	IngestionStatsResponse,
	InvalidEvent,
	LocomotiveCurrentResponse,
	SystemMetricsResponse,
	TelemetryEvent,
	TelemetryIngestResponse,
)

router = APIRouter(tags=["telemetry"])


def _utcnow() -> datetime:
	return datetime.now(timezone.utc)


def _to_event_dict(event: TelemetryEvent) -> dict[str, Any]:
	payload = event.model_dump(mode="json")
	payload["timestamp"] = event.timestamp.astimezone(timezone.utc).isoformat()
	payload["ingestion_time"] = _utcnow().isoformat()
	return payload


async def _ensure_locomotive(db: AsyncSession, locomotive_id: str) -> None:
	row = (await db.execute(select(Locomotive).where(Locomotive.id == locomotive_id))).scalar_one_or_none()
	if row is None:
		db.add(Locomotive(id=locomotive_id, display_name=locomotive_id))


@router.post("/ingest/telemetry", response_model=TelemetryIngestResponse)
async def ingest_telemetry(
	payload: dict[str, Any] | list[dict[str, Any]] = Body(...),
	db: AsyncSession = Depends(get_db),
) -> TelemetryIngestResponse:
	raw_items = payload if isinstance(payload, list) else [payload]

	valid_events: list[TelemetryEvent] = []
	invalid_items: list[InvalidEvent] = []

	for index, item in enumerate(raw_items):
		try:
			valid_events.append(TelemetryEvent.model_validate(item))
		except ValidationError as exc:
			invalid_items.append(InvalidEvent(index=index, error=str(exc)))

	if not valid_events:
		metrics.record_ingested(valid=0, invalid=len(invalid_items), dropped=0)
		raise HTTPException(
			status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
			detail={
				"accepted": 0,
				"rejected": len(invalid_items),
				"invalid_items": [item.model_dump() for item in invalid_items],
			},
		)

	started = time.perf_counter()
	for event in valid_events:
		await _ensure_locomotive(db, event.locomotive_id)
		event_payload = event.model_dump(exclude={"ingestion_time"})
		record = TelemetryEventRecord(**event_payload, ingestion_time=_utcnow())
		db.add(record)

		snapshot_payload = _to_event_dict(event)
		snapshot = (
			await db.execute(
				select(CurrentSnapshot).where(CurrentSnapshot.locomotive_id == event.locomotive_id)
			)
		).scalar_one_or_none()

		if snapshot is None:
			snapshot = CurrentSnapshot(
				locomotive_id=event.locomotive_id,
				payload=snapshot_payload,
				event_timestamp=event.timestamp,
			)
			db.add(snapshot)
		else:
			snapshot.payload = snapshot_payload
			snapshot.event_timestamp = event.timestamp
			snapshot.updated_at = _utcnow()

		stat = (
			await db.execute(select(IngestionStat).where(IngestionStat.locomotive_id == event.locomotive_id))
		).scalar_one_or_none()
		if stat is None:
			stat = IngestionStat(
				locomotive_id=event.locomotive_id,
				total_events=0,
				valid_events=0,
				invalid_events=0,
			)
			db.add(stat)
		stat.total_events = (stat.total_events or 0) + 1
		stat.valid_events = (stat.valid_events or 0) + 1
		stat.last_error = None
		stat.last_ingest_time = _utcnow()

		metrics.record_event_seen(event.locomotive_id, event.timestamp)
		await publish_event(snapshot_payload)

	for item in invalid_items:
		# Attribute invalid records to a synthetic bucket while preserving per-item errors.
		stat = (await db.execute(select(IngestionStat).where(IngestionStat.locomotive_id == "_invalid"))).scalar_one_or_none()
		if stat is None:
			stat = IngestionStat(
				locomotive_id="_invalid",
				total_events=0,
				valid_events=0,
				invalid_events=0,
			)
			db.add(stat)
		stat.total_events = (stat.total_events or 0) + 1
		stat.invalid_events = (stat.invalid_events or 0) + 1
		stat.last_error = item.error
		stat.last_ingest_time = _utcnow()

	metrics.record_db_write_latency((time.perf_counter() - started) * 1000)
	metrics.record_ingested(valid=len(valid_events), invalid=len(invalid_items), dropped=0)

	return TelemetryIngestResponse(
		accepted=len(valid_events),
		rejected=len(invalid_items),
		invalid_items=invalid_items,
	)


@router.get("/locomotives")
async def list_locomotives(db: AsyncSession = Depends(get_db)) -> list[dict[str, str]]:
	rows = (await db.execute(select(Locomotive).order_by(Locomotive.id.asc()))).scalars().all()
	return [{"id": row.id, "display_name": row.display_name or row.id} for row in rows]


@router.get("/locomotives/{locomotive_id}/current", response_model=LocomotiveCurrentResponse)
async def get_current(
	locomotive_id: str,
	db: AsyncSession = Depends(get_db),
) -> LocomotiveCurrentResponse:
	row = (
		await db.execute(select(CurrentSnapshot).where(CurrentSnapshot.locomotive_id == locomotive_id))
	).scalar_one_or_none()
	event = TelemetryEvent.model_validate(row.payload) if row is not None else None
	return LocomotiveCurrentResponse(locomotive_id=locomotive_id, event=event)


@router.get("/locomotives/{locomotive_id}/history")
async def get_history(
	locomotive_id: str,
	from_ts: datetime = Query(..., alias="from"),
	to_ts: datetime = Query(..., alias="to"),
	limit: int = Query(default=500, ge=1, le=10_000),
	db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
	rows = (
		await db.execute(
			select(TelemetryEventRecord)
			.where(
				TelemetryEventRecord.locomotive_id == locomotive_id,
				TelemetryEventRecord.timestamp >= from_ts,
				TelemetryEventRecord.timestamp <= to_ts,
			)
			.order_by(TelemetryEventRecord.timestamp.desc())
			.limit(limit)
		)
	).scalars().all()

	return [
		TelemetryEvent.model_validate(
			{
				**row.__dict__,
				"active_fault_codes": row.active_fault_codes or [],
			}
		).model_dump(mode="json")
		for row in reversed(rows)
	]


@router.get("/locomotives/{locomotive_id}/latest-metrics")
async def get_latest_metrics(
	locomotive_id: str,
	db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
	row = (
		await db.execute(select(CurrentSnapshot).where(CurrentSnapshot.locomotive_id == locomotive_id))
	).scalar_one_or_none()
	if row is None:
		raise HTTPException(status_code=404, detail="No telemetry for locomotive")

	payload = row.payload
	return {
		"locomotive_id": locomotive_id,
		"speed_kph": payload.get("speed_kph"),
		"allowed_speed_kph": payload.get("allowed_speed_kph"),
		"traction_mode": payload.get("traction_mode"),
		"traction_power_kw": payload.get("traction_power_kw"),
		"regen_power_kw": payload.get("regen_power_kw"),
		"transformer_temp_c": payload.get("transformer_temp_c"),
		"converter_temp_c": payload.get("converter_temp_c"),
		"traction_motor_temp_c": payload.get("traction_motor_temp_c"),
		"axle_bearing_temp_c": payload.get("axle_bearing_temp_c"),
		"pneumatic_pressure_bar": payload.get("pneumatic_pressure_bar"),
		"signal_quality": payload.get("signal_quality"),
		"data_quality": payload.get("data_quality"),
		"timestamp": payload.get("timestamp"),
	}


@router.get("/system/metrics", response_model=SystemMetricsResponse)
async def get_system_metrics() -> SystemMetricsResponse:
	return SystemMetricsResponse(**metrics.snapshot())


@router.get("/ingestion/stats")
async def get_ingestion_stats(db: AsyncSession = Depends(get_db)) -> list[IngestionStatsResponse]:
	rows = (await db.execute(select(IngestionStat).order_by(IngestionStat.locomotive_id.asc()))).scalars().all()
	return [IngestionStatsResponse.model_validate(row) for row in rows if row.locomotive_id != "_invalid"]


@router.get("/locomotives/{locomotive_id}/ingestion-stats", response_model=IngestionStatsResponse)
async def get_locomotive_ingestion_stats(
	locomotive_id: str,
	db: AsyncSession = Depends(get_db),
) -> IngestionStatsResponse:
	row = (
		await db.execute(select(IngestionStat).where(IngestionStat.locomotive_id == locomotive_id))
	).scalar_one_or_none()
	if row is None:
		raise HTTPException(status_code=404, detail="No ingestion stats for locomotive")
	return IngestionStatsResponse.model_validate(row)
