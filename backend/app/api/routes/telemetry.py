from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_db
from ...core.route_matcher import match_position
from ...core.runtime_state import cached_routes, metrics, publish_event
from ...models.alert import LocomotiveWarning
from ...models.route import LocomotivePosition
from ...models.telemetry import CurrentSnapshot, IngestionStat, Locomotive, TelemetryEventRecord
from ...schemas.telemetry import (
	ActiveWarningResponse,
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


def _compute_derived_route_metrics(
	*,
	speed_kph: float,
	route_id: str | None,
	progress_pct: float | None,
	route_segment: str | None,
) -> dict[str, Any]:
	if route_id is None or progress_pct is None:
		# Fallback for demo mode: when snapping misses but simulator still sends
		# route_segment like "ALA-NUR:012", infer progress from segment index.
		route_id, progress_pct = _derive_progress_from_route_segment(route_segment)

	if route_id is None or progress_pct is None:
		return {
			"route_progress_percent": None,
			"distance_to_destination_km": None,
			"eta_seconds": None,
			"eta_timestamp": None,
		}

	route = next((r for r in cached_routes if r.id == route_id), None)
	if route is None or not route.total_length_km:
		return {
			"route_progress_percent": max(0.0, min(100.0, float(progress_pct))),
			"distance_to_destination_km": None,
			"eta_seconds": None,
			"eta_timestamp": None,
		}

	progress = max(0.0, min(100.0, float(progress_pct)))
	remaining_km = max(0.0, float(route.total_length_km) * (1.0 - progress / 100.0))

	if remaining_km <= 0.01:
		eta_seconds = 0
		eta_timestamp = _utcnow()
	elif speed_kph < 3.0:
		eta_seconds = None
		eta_timestamp = None
	else:
		eta_seconds = max(0, int(round((remaining_km / speed_kph) * 3600.0)))
		eta_timestamp = _utcnow() + timedelta(seconds=eta_seconds)

	return {
		"route_progress_percent": progress,
		"distance_to_destination_km": round(remaining_km, 3),
		"eta_seconds": eta_seconds,
		"eta_timestamp": eta_timestamp.isoformat() if eta_timestamp is not None else None,
	}


def _derive_progress_from_route_segment(route_segment: str | None) -> tuple[str | None, float | None]:
	if not route_segment:
		return None, None

	try:
		route_code, seg_idx_raw = route_segment.split(":", 1)
		match = re.match(r"\s*(\d+)", seg_idx_raw)
		if match is None:
			return None, None
		seg_idx = int(match.group(1))
	except (ValueError, AttributeError):
		return None, None

	route = next((r for r in cached_routes if r.code == route_code), None)
	if route is None:
		return None, None

	segments_total = max(1, len(route.coordinates) - 1)
	clamped_idx = max(0, min(seg_idx, segments_total))
	progress_pct = (clamped_idx / segments_total) * 100.0
	return route.id, progress_pct


def _warning_definition(
	locomotive_id: str,
	rule_id: str,
	source: str,
	target_type: str,
	target_id: str,
	severity: str,
	title: str,
	message: str,
	recommended_action: str,
) -> dict[str, Any]:
	return {
		"warning_id": f"{source}:{target_type}:{target_id}:{rule_id}",
		"locomotive_id": locomotive_id,
		"rule_id": rule_id,
		"source": source,
		"target_type": target_type,
		"target_id": target_id,
		"severity": severity,
		"title": title,
		"message": message,
		"recommended_action": recommended_action,
		"created_by": None,
		"metadata": None,
		"expires_at": None,
		"status": "active",
		"cleared_at": None,
		"active": True,
	}


def _compute_warning_candidates(event: TelemetryEvent) -> dict[str, dict[str, Any]]:
	candidates: dict[str, dict[str, Any]] = {}
	locomotive_id = event.locomotive_id
	fault_codes = {code.lower() for code in (event.active_fault_codes or [])}

	if "upcoming_bad_track" in fault_codes:
		candidates["upcoming_bad_track"] = _warning_definition(
			locomotive_id=locomotive_id,
			rule_id="upcoming_bad_track",
			source="system",
			target_type="locomotive",
			target_id=locomotive_id,
			severity="warning",
			title="Скоро участок с плохим состоянием пути",
			message="По маршруту впереди ожидается участок с ухудшенным состоянием пути.",
			recommended_action="Снизьте скорость и контролируйте плавность движения",
		)

	if event.allowed_speed_kph is not None and event.speed_kph > event.allowed_speed_kph + 1.0:
		overspeed_by = event.speed_kph - event.allowed_speed_kph
		severity = "critical" if overspeed_by >= 10.0 else "warning"
		candidates["overspeed"] = _warning_definition(
			locomotive_id=locomotive_id,
			rule_id="overspeed",
			source="system",
			target_type="locomotive",
			target_id=locomotive_id,
			severity=severity,
			title="Превышение разрешенной скорости",
			message=f"Current speed {event.speed_kph:.1f} kph exceeds allowed {event.allowed_speed_kph:.1f} kph.",
			recommended_action="Снизьте скорость до допустимой",
		)

	max_temp = max(
		float(event.transformer_temp_c or -999.0),
		float(event.converter_temp_c or -999.0),
		float(event.traction_motor_temp_c or -999.0),
		float(event.axle_bearing_temp_c or -999.0),
	)
	if max_temp >= 95.0:
		severity = "critical" if max_temp >= 110.0 else "warning"
		candidates["high_temperature"] = _warning_definition(
			locomotive_id=locomotive_id,
			rule_id="high_temperature",
			source="system",
			target_type="locomotive",
			target_id=locomotive_id,
			severity=severity,
			title="Повышенная температура тягового двигателя",
			message=f"Температура тягового двигателя достигла {float(event.traction_motor_temp_c or max_temp):.1f} C.",
			recommended_action="Снизьте тяговую нагрузку",
		)

	min_quality = min(
		float(event.signal_quality if event.signal_quality is not None else 1.0),
		float(event.data_quality if event.data_quality is not None else 1.0),
	)
	if min_quality < 0.9:
		severity = "critical" if min_quality < 0.75 else "warning"
		candidates["low_signal_quality"] = _warning_definition(
			locomotive_id=locomotive_id,
			rule_id="low_signal_quality",
			source="system",
			target_type="locomotive",
			target_id=locomotive_id,
			severity=severity,
			title="Низкое качество сигнала",
			message=f"Качество сигнала снижено до {min_quality:.2f}.",
			recommended_action="Учитывайте возможную неточность показаний",
		)

	if event.catenary_voltage_kv is not None and event.catenary_voltage_kv < 20.0:
		severity = "critical" if event.catenary_voltage_kv < 17.0 else "warning"
		candidates["voltage_sag"] = _warning_definition(
			locomotive_id=locomotive_id,
			rule_id="voltage_sag",
			source="system",
			target_type="locomotive",
			target_id=locomotive_id,
			severity=severity,
			title="Просадка напряжения контактной сети",
			message=f"Напряжение контактной сети составляет {event.catenary_voltage_kv:.1f} кВ.",
			recommended_action="Учитывайте возможное снижение тяги",
		)

	max_vibration = max(float(event.vibration_motor or 0.0), float(event.vibration_gearbox or 0.0))
	if max_vibration >= 2.0:
		severity = "critical" if max_vibration >= 4.0 else "warning"
		candidates["high_vibration"] = _warning_definition(
			locomotive_id=locomotive_id,
			rule_id="high_vibration",
			source="system",
			target_type="locomotive",
			target_id=locomotive_id,
			severity=severity,
			title="Повышенная вибрация",
			message=f"Peak vibration is {max_vibration:.2f}.",
			recommended_action="Снизьте скорость и контролируйте состояние локомотива",
		)

	if event.track_condition in {"rough", "bad", "maintenance_zone"}:
		severity = "critical" if event.track_condition in {"bad", "maintenance_zone"} else "warning"
		candidates["track_condition_alert"] = _warning_definition(
			locomotive_id=locomotive_id,
			rule_id="track_condition_alert",
			source="system",
			target_type="locomotive",
			target_id=locomotive_id,
			severity=severity,
			title="Ухудшенные условия пути",
			message=f"Текущий участок пути отмечен как {event.track_condition}.",
			recommended_action="Снизьте скорость и контролируйте вибрации ходовой части",
		)

	if event.weather_condition in {"rain", "snow", "fog", "wind"}:
		severity = "critical" if event.weather_condition in {"snow", "fog"} else "warning"
		candidates["weather_condition_alert"] = _warning_definition(
			locomotive_id=locomotive_id,
			rule_id="weather_condition_alert",
			source="system",
			target_type="locomotive",
			target_id=locomotive_id,
			severity=severity,
			title="Неблагоприятные погодные условия",
			message=f"Текущие погодные условия: {event.weather_condition}.",
			recommended_action="Соблюдайте пониженные скоростные ограничения и повышенную дистанцию",
		)

	return candidates


def _to_warning_response(row: LocomotiveWarning) -> ActiveWarningResponse:
	return ActiveWarningResponse(
		warning_id=row.warning_id,
		locomotive_id=row.locomotive_id,
		rule_id=row.rule_id,
		source=row.source,
		target_type=row.target_type,
		target_id=row.target_id,
		severity=row.severity,
		title=row.title,
		message=row.message,
		recommended_action=row.recommended_action,
		status=row.status,
		created_by=row.created_by,
		metadata=row.warning_metadata,
		expires_at=row.expires_at,
		cleared_at=row.cleared_at,
		active=row.active,
		first_seen_at=row.first_seen_at,
		last_seen_at=row.last_seen_at,
	)


async def _expire_outdated_warnings(db: AsyncSession, *, locomotive_id: str | None = None) -> None:
	now = _utcnow()
	query = select(LocomotiveWarning).where(
		LocomotiveWarning.active.is_(True),
		LocomotiveWarning.expires_at.is_not(None),
		LocomotiveWarning.expires_at <= now,
	)
	if locomotive_id is not None:
		query = query.where(LocomotiveWarning.locomotive_id == locomotive_id)

	rows = (await db.execute(query)).scalars().all()
	for row in rows:
		row.active = False
		row.status = "expired"
		row.cleared_at = now
		row.last_seen_at = now


async def _sync_warnings_for_event(db: AsyncSession, event: TelemetryEvent) -> list[LocomotiveWarning]:
	now = _utcnow()
	candidates = _compute_warning_candidates(event)
	candidate_ids = set(candidates.keys())
	await _expire_outdated_warnings(db, locomotive_id=event.locomotive_id)

	rows = (
		await db.execute(
			select(LocomotiveWarning).where(
				LocomotiveWarning.locomotive_id == event.locomotive_id,
				LocomotiveWarning.source == "system",
				LocomotiveWarning.target_type == "locomotive",
			)
		)
	).scalars().all()
	rows_by_rule = {row.rule_id: row for row in rows}

	for rule_id, warning in candidates.items():
		row = rows_by_rule.get(rule_id)
		if row is None:
			row = LocomotiveWarning(
				warning_id=warning["warning_id"],
				locomotive_id=warning["locomotive_id"],
				rule_id=warning["rule_id"],
				source=warning["source"],
				target_type=warning["target_type"],
				target_id=warning["target_id"],
				severity=warning["severity"],
				title=warning["title"],
				message=warning["message"],
				recommended_action=warning["recommended_action"],
				created_by=warning["created_by"],
				warning_metadata=warning["metadata"],
				expires_at=warning["expires_at"],
				status=warning["status"],
				cleared_at=warning["cleared_at"],
				active=True,
				first_seen_at=now,
				last_seen_at=now,
			)
			db.add(row)
			rows_by_rule[rule_id] = row
		else:
			row.severity = warning["severity"]
			row.title = warning["title"]
			row.message = warning["message"]
			row.recommended_action = warning["recommended_action"]
			row.expires_at = warning["expires_at"]
			row.status = "active"
			row.cleared_at = None
			row.active = True
			row.last_seen_at = now

	for rule_id, row in rows_by_rule.items():
		if rule_id not in candidate_ids and row.active:
			row.active = False
			row.status = "cleared"
			row.cleared_at = now
			row.last_seen_at = now

	all_active = await _get_active_warning_rows(db, event.locomotive_id)
	return all_active


async def _get_active_warning_rows(db: AsyncSession, locomotive_id: str) -> list[LocomotiveWarning]:
	await _expire_outdated_warnings(db, locomotive_id=locomotive_id)
	now = _utcnow()

	loco_rows = (
		await db.execute(
			select(LocomotiveWarning)
			.where(
				LocomotiveWarning.locomotive_id == locomotive_id,
				LocomotiveWarning.active.is_(True),
			)
			.where(
				(LocomotiveWarning.expires_at.is_(None))
				| (LocomotiveWarning.expires_at > now)
			)
		)
	).scalars().all()
	rows = list(loco_rows)
	rows.sort(key=lambda item: item.last_seen_at, reverse=True)
	return rows


async def _get_active_warnings(db: AsyncSession, locomotive_id: str) -> list[ActiveWarningResponse]:
	rows = await _get_active_warning_rows(db, locomotive_id)
	return [_to_warning_response(row) for row in rows]


async def _get_warning_history(db: AsyncSession, locomotive_id: str) -> list[ActiveWarningResponse]:
	await _expire_outdated_warnings(db, locomotive_id=locomotive_id)
	rows = (
		await db.execute(
			select(LocomotiveWarning)
			.where(LocomotiveWarning.locomotive_id == locomotive_id)
			.order_by(LocomotiveWarning.first_seen_at.desc())
		)
	).scalars().all()
	return [_to_warning_response(row) for row in rows]


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
		active_warnings = await _sync_warnings_for_event(db, event)
		event_payload = event.model_dump(
			exclude={
				"ingestion_time",
				"route_progress_percent",
				"distance_to_destination_km",
				"eta_seconds",
				"eta_timestamp",
			}
		)
		record = TelemetryEventRecord(**event_payload, ingestion_time=_utcnow())
		db.add(record)

		snapshot_payload = _to_event_dict(event)
		snapshot_payload["active_warnings"] = [
			_to_warning_response(row).model_dump(mode="json") for row in active_warnings
		]
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

		snap = None

		# ── upsert LocomotivePosition so /api/map/fleet stays live ─────
		if event.gps_lat is not None and event.gps_lon is not None:
			snap = match_position(event.gps_lat, event.gps_lon, cached_routes)
			lp = (
				await db.execute(
					select(LocomotivePosition).where(
						LocomotivePosition.locomotive_id == event.locomotive_id
					)
				)
			).scalar_one_or_none()
			if lp is None:
				lp = LocomotivePosition(locomotive_id=event.locomotive_id)
				db.add(lp)
			lp.lat = event.gps_lat
			lp.lng = event.gps_lon
			lp.speed = event.speed_kph
			lp.updated_at = _utcnow()
			if snap is not None:
				lp.route_id = snap.route_id
				lp.route_code = snap.route_code
				lp.route_name = snap.route_name
				lp.snapped_lat = snap.snapped_lat
				lp.snapped_lng = snap.snapped_lng
				lp.distance_to_route_m = snap.distance_km * 1000
				lp.progress_pct = snap.progress_pct
			else:
				lp.route_id = None
				lp.route_code = None
				lp.route_name = None
				lp.snapped_lat = None
				lp.snapped_lng = None
				lp.distance_to_route_m = None
				lp.progress_pct = None

		derived = _compute_derived_route_metrics(
			speed_kph=float(event.speed_kph),
			route_id=(snap.route_id if snap is not None else None),
			progress_pct=(snap.progress_pct if snap is not None else None),
			route_segment=event.route_segment,
		)
		snapshot_payload.update(derived)
		if snapshot is not None:
			snapshot.payload = snapshot_payload

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
	active_warnings = await _get_active_warnings(db, locomotive_id)
	return LocomotiveCurrentResponse(
		locomotive_id=locomotive_id,
		event=event,
		active_warnings=active_warnings,
	)


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


@router.get("/locomotives/{locomotive_id}/warnings", response_model=list[ActiveWarningResponse])
async def get_locomotive_warnings(
	locomotive_id: str,
	db: AsyncSession = Depends(get_db),
) -> list[ActiveWarningResponse]:
	return await _get_warning_history(db, locomotive_id)


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
