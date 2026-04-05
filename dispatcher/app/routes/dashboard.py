"""Fleet and dashboard endpoints."""

from __future__ import annotations

import io
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from sqlalchemy import and_, desc, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import TokenClaims, get_current_user, issue_access_token
from app.database import get_db
from app.models.alert import LocomotiveWarning
from app.models.route import LocomotivePosition, Route
from app.models.telemetry import Locomotive
from app.models.telemetry_ingest import LocomotiveTelemetry
from app.models.user import AuthSession, DriverAccount
from app.schemas import (
    DashboardMetrics,
    FleetStatusResponse,
    ListRoutesResponse,
    LocoStatusInfo,
    RouteInfo,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dispatcher", tags=["dispatcher"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/fleet", response_model=FleetStatusResponse, summary="Get fleet status")
async def get_fleet_status(
    db: AsyncSession = Depends(get_db),
    _: TokenClaims = Depends(get_current_user),
) -> FleetStatusResponse:
    """Get current status of all locomotives in the fleet."""
    try:
        loco_result = await db.execute(select(Locomotive))
        locomotives = loco_result.scalars().all()

        positions_result = await db.execute(select(LocomotivePosition))
        positions_map: dict[str, LocomotivePosition] = {
            p.locomotive_id: p for p in positions_result.scalars().all()
        }

        now = _utcnow()
        warnings_result = await db.execute(
            select(LocomotiveWarning).where(
                and_(
                    LocomotiveWarning.active == True,
                    (LocomotiveWarning.expires_at == None) | (LocomotiveWarning.expires_at > now),
                )
            )
        )
        critical_by_loco: dict[str, int] = {}
        noncrit_by_loco: dict[str, int] = {}
        for w in warnings_result.scalars().all():
            lid = w.locomotive_id
            sev = (w.severity or "").lower()
            if sev == "critical":
                critical_by_loco[lid] = critical_by_loco.get(lid, 0) + 1
            else:
                noncrit_by_loco[lid] = noncrit_by_loco.get(lid, 0) + 1

        fleet_list: list[LocoStatusInfo] = []
        online_count = 0

        for loco in locomotives:
            pos = positions_map.get(loco.id)
            is_online = False
            if pos and pos.updated_at:
                is_online = (now - pos.updated_at).total_seconds() < 300

            if is_online:
                online_count += 1

            crit_n = critical_by_loco.get(loco.id, 0)
            other_n = noncrit_by_loco.get(loco.id, 0)
            fleet_list.append(
                LocoStatusInfo(
                    locomotive_id=loco.id,
                    display_name=loco.display_name or loco.id,
                    lat=pos.lat if pos else 0.0,
                    lng=pos.lng if pos else 0.0,
                    speed_kph=pos.speed if pos else 0.0,
                    heading=pos.heading if pos else None,
                    route_code=pos.route_code if pos else None,
                    route_name=pos.route_name if pos else None,
                    progress_pct=pos.progress_pct if pos else None,
                    is_online=is_online,
                    active_warnings_count=crit_n + other_n,
                    active_critical_count=crit_n,
                    active_noncritical_count=other_n,
                    last_updated=pos.updated_at if pos else now,
                )
            )

        return FleetStatusResponse(
            locomotives=fleet_list,
            total_locomotives=len(locomotives),
            locomotives_online=online_count,
            active_warnings_count=sum(critical_by_loco.values()) + sum(noncrit_by_loco.values()),
        )
    except Exception as exc:
        logger.error(f"Error getting fleet status: {exc}")
        return FleetStatusResponse(locomotives=[], total_locomotives=0, locomotives_online=0, active_warnings_count=0)


@router.get("/debug/warnings", summary="DEBUG: Get all warnings (no auth)")
async def debug_warnings(
    db: AsyncSession = Depends(get_db),
):
    """Debug endpoint to check warnings in database."""
    try:
        result = await db.execute(select(LocomotiveWarning))
        warnings = result.scalars().all()
        return {
            "count": len(warnings),
            "warnings": [
                {
                    "warning_id": w.warning_id,
                    "locomotive_id": w.locomotive_id,
                    "severity": w.severity,
                    "active": w.active,
                    "title": w.title,
                    "first_seen_at": w.first_seen_at.isoformat() if w.first_seen_at else None,
                }
                for w in warnings[:20]
            ]
        }
    except Exception as exc:
        logger.error(f"Error in debug endpoint: {exc}")
        return {"error": str(exc)}


@router.get("/debug/token", summary="DEBUG: Get test token (no auth)")
async def debug_token(
    db: AsyncSession = Depends(get_db),
):
    """Debug endpoint to get a test token without session validation."""
    try:
        session_id = str(uuid4())
        user_id = "debug-test-user"
        
        # Check if DriverAccount exists, create if not
        user_result = await db.execute(
            select(DriverAccount).where(DriverAccount.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        if user is None:
            user = DriverAccount(
                id=user_id,
                company_id="TEST_COMPANY",
                password_hash="pbkdf2_sha256$390000$0000000000000000$0000000000000000000000000000000000000000000000000000000000000000",
                name="Debug Test",
                role="Admin",
                locomotive_id=None,
                is_active=True,
            )
            db.add(user)
            await db.flush()
        
        token, expires_at, _ = issue_access_token(
            user_id=user_id,
            company_id="TEST_COMPANY",
            name="Debug Test",
            role="Admin",
            locomotive_id=None,
            session_id=session_id,
        )
        
        # Create AuthSession in database so token validation passes
        auth_session = AuthSession(
            id=session_id,
            user_id=user_id,
            refresh_jti=str(uuid4()),
            expires_at=expires_at,
        )
        db.add(auth_session)
        await db.commit()
        
        return {"access_token": token, "token_type": "bearer"}
    except Exception as exc:
        logger.error(f"Error generating token: {exc}")
        import traceback
        traceback.print_exc()
        return {"error": str(exc)}


@router.get("/map/routes", summary="GeoJSON routes for dispatcher map (auth)")
async def dispatcher_map_routes_geojson(
    db: AsyncSession = Depends(get_db),
    _: TokenClaims = Depends(get_current_user),
) -> dict[str, Any]:
    """Same structure as main backend `/api/map/routes` for Leaflet."""
    result = await db.execute(select(Route))
    rows = result.scalars().all()
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": r.id,
                "geometry": {"type": "LineString", "coordinates": r.coordinates},
                "properties": {
                    "id": r.id,
                    "code": r.code,
                    "name": r.name,
                    "total_length_km": r.total_length_km,
                },
            }
            for r in rows
        ],
    }


@router.get("/routes", response_model=ListRoutesResponse, summary="Get all routes")
async def get_routes(
    db: AsyncSession = Depends(get_db),
    _: TokenClaims = Depends(get_current_user),
) -> ListRoutesResponse:
    try:
        result = await db.execute(select(Route))
        routes = result.scalars().all()
        return ListRoutesResponse(
            routes=[RouteInfo(code=r.code, name=r.name, total_length_km=r.total_length_km) for r in routes],
            total_count=len(routes),
        )
    except Exception as exc:
        logger.error(f"Error getting routes: {exc}")
        return ListRoutesResponse(routes=[], total_count=0)


@router.get("/metrics", response_model=DashboardMetrics, summary="Get dashboard metrics")
async def get_dashboard_metrics(
    db: AsyncSession = Depends(get_db),
    _: TokenClaims = Depends(get_current_user),
) -> DashboardMetrics:
    try:
        loco_result = await db.execute(select(Locomotive))
        total_locos = len(loco_result.scalars().all())

        now = _utcnow()
        five_min_ago = now - timedelta(minutes=5)
        online_result = await db.execute(
            select(LocomotivePosition).where(LocomotivePosition.updated_at > five_min_ago)
        )
        online_locos = len(online_result.scalars().all())

        warnings_result = await db.execute(
            select(LocomotiveWarning).where(
                and_(
                    LocomotiveWarning.active == True,
                    (LocomotiveWarning.expires_at == None) | (LocomotiveWarning.expires_at > now),
                )
            )
        )
        all_warnings = warnings_result.scalars().all()
        critical_count = sum(1 for w in all_warnings if w.severity == "critical")

        positions_result = await db.execute(select(LocomotivePosition))
        all_positions = positions_result.scalars().all()
        avg_speed = sum(p.speed for p in all_positions) / len(all_positions) if all_positions else 0.0

        return DashboardMetrics(
            total_locomotives=total_locos,
            online_locomotives=online_locos,
            total_active_warnings=len(all_warnings),
            critical_warnings_count=critical_count,
            total_events_today=0,
            avg_speed_kph=avg_speed,
            system_uptime_seconds=0.0,
        )
    except Exception as exc:
        logger.error(f"Error getting dashboard metrics: {exc}")
        return DashboardMetrics(
            total_locomotives=0, online_locomotives=0, total_active_warnings=0,
            critical_warnings_count=0, total_events_today=0, avg_speed_kph=0.0,
            system_uptime_seconds=0.0,
        )


@router.get("/locomotive/{locomotive_id}", summary="Get locomotive details")
async def get_locomotive_details(
    locomotive_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenClaims = Depends(get_current_user),
) -> dict:
    try:
        loco_result = await db.execute(select(Locomotive).where(Locomotive.id == locomotive_id))
        loco = loco_result.scalar_one_or_none()
        if not loco:
            return {"error": "Locomotive not found"}

        pos_result = await db.execute(
            select(LocomotivePosition).where(LocomotivePosition.locomotive_id == locomotive_id)
        )
        pos = pos_result.scalar_one_or_none()

        now = _utcnow()
        warnings_result = await db.execute(
            select(LocomotiveWarning).where(
                and_(
                    LocomotiveWarning.locomotive_id == locomotive_id,
                    LocomotiveWarning.active == True,
                    (LocomotiveWarning.expires_at == None) | (LocomotiveWarning.expires_at > now),
                )
            )
        )
        warnings = warnings_result.scalars().all()

        is_online = bool(pos and (now - pos.updated_at).total_seconds() < 300)
        return {
            "locomotive_id": loco.id,
            "name": loco.display_name,
            "status": "online" if is_online else "offline",
            "current_position": {
                "lat": pos.lat if pos else None,
                "lng": pos.lng if pos else None,
                "speed_kph": pos.speed if pos else 0,
                "heading": pos.heading if pos else 0,
                "route_code": pos.route_code if pos else None,
                "route_name": pos.route_name if pos else None,
                "last_updated": pos.updated_at.isoformat() if pos else None,
            },
            "active_warnings_count": len(warnings),
            "warnings": [
                {
                    "warning_id": w.warning_id,
                    "rule_id": w.rule_id,
                    "severity": w.severity,
                    "title": w.title,
                    "message": w.message,
                    "created_by": w.created_by,
                    "expires_at": w.expires_at.isoformat() if w.expires_at else None,
                    "first_seen_at": w.first_seen_at.isoformat(),
                }
                for w in warnings
            ],
        }
    except Exception as exc:
        logger.error(f"Error getting locomotive details for {locomotive_id}: {exc}")
        return {"error": str(exc)}


@router.get("/locomotives/{locomotive_id}/report/15min", summary="Download 15-min telemetry PDF report")
async def generate_locomotive_report(
    locomotive_id: str,
    db: AsyncSession = Depends(get_db),
    _: TokenClaims = Depends(get_current_user),
):
    """Generate a PDF report with 15-minute locomotive telemetry summary and recent events."""
    try:
        # Fetch locomotive info from dispatcher db
        loco_result = await db.execute(select(Locomotive).where(Locomotive.id == locomotive_id))
        locomotive = loco_result.scalar_one_or_none()
        if not locomotive:
            return {"error": f"Locomotive {locomotive_id} not found"}, 404

        # Calculate 15-minute time range
        now = datetime.now(timezone.utc)
        fifteen_min_ago = now - timedelta(minutes=15)
        
        # Fetch telemetry history from backend
        backend_url = os.getenv("BACKEND_URL", "http://backend:8000")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{backend_url}/api/locomotives/{locomotive_id}/history",
                    params={
                        "from": fifteen_min_ago.isoformat(),
                        "to": now.isoformat(),
                        "limit": 500,
                    },
                    timeout=5.0
                )
                if response.status_code != 200:
                    return {"error": f"No telemetry data available for {locomotive_id}"}, 404
                events_data = response.json()
            except Exception as exc:
                logger.error(f"Error fetching from backend: {exc}")
                return {"error": "Failed to fetch telemetry from backend"}, 503

        if not events_data:
            return {"error": f"No telemetry data for {locomotive_id} in last 15 minutes"}, 404

        # Create PDF document
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=16,
            textColor=colors.HexColor("#1f2937"),
            spaceAfter=12,
            fontName="Helvetica-Bold",
        )
        heading_style = ParagraphStyle(
            "CustomHeading",
            parent=styles["Heading2"],
            fontSize=12,
            textColor=colors.HexColor("#374151"),
            spaceAfter=10,
            spaceBefore=12,
            fontName="Helvetica-Bold",
        )
        
        # Title
        story.append(Paragraph(f"15-Minute Report: {locomotive.display_name}", title_style))
        story.append(Spacer(1, 0.15 * inch))
        
        # Summary metrics
        story.append(Paragraph("Summary Metrics (Last 15 Minutes)", heading_style))
        
        speeds = [e.get("speed_kph") or 0 for e in events_data]
        temperatures = [e.get("engine_temperature_c") or 0 for e in events_data if e.get("engine_temperature_c")]
        brake_pressures = [e.get("brake_cylinder_pressure_bar") or 0 for e in events_data if e.get("brake_cylinder_pressure_bar")]
        
        # Temperature metrics
        transformer_temps = [e.get("transformer_temp_c") or 0 for e in events_data if e.get("transformer_temp_c")]
        converter_temps = [e.get("converter_temp_c") or 0 for e in events_data if e.get("converter_temp_c")]
        motor_temps = [e.get("traction_motor_temp_c") or 0 for e in events_data if e.get("traction_motor_temp_c")]
        axle_temps = [e.get("axle_bearing_temp_c") or 0 for e in events_data if e.get("axle_bearing_temp_c")]
        brake_temps = [e.get("brakes_temperature_c") or 0 for e in events_data if e.get("brakes_temperature_c")]
        
        # Pressure metrics
        brake_pipe_pressures = [e.get("brake_pipe_pressure_bar") or 0 for e in events_data if e.get("brake_pipe_pressure_bar")]
        pneumatic_pressures = [e.get("pneumatic_pressure_bar") or 0 for e in events_data if e.get("pneumatic_pressure_bar")]
        catenary_voltages = [e.get("catenary_voltage_kv") or 0 for e in events_data if e.get("catenary_voltage_kv")]
        
        # Power metrics
        traction_currents = [e.get("traction_current_a") or 0 for e in events_data if e.get("traction_current_a")]
        traction_powers = [e.get("traction_power_kw") or 0 for e in events_data if e.get("traction_power_kw")]
        regen_powers = [e.get("regen_power_kw") or 0 for e in events_data if e.get("regen_power_kw")]
        
        # Vibration metrics
        vibration_motors = [e.get("vibration_motor") or 0 for e in events_data if e.get("vibration_motor")]
        vibration_gearboxes = [e.get("vibration_gearbox") or 0 for e in events_data if e.get("vibration_gearbox")]
        
        # Compressor metrics
        compressor_cycles = [e.get("compressor_cycles_per_hour") or 0 for e in events_data if e.get("compressor_cycles_per_hour")]
        
        # Quality metrics
        signal_qualities = [e.get("signal_quality") or 0 for e in events_data if e.get("signal_quality")]
        data_qualities = [e.get("data_quality") or 0 for e in events_data if e.get("data_quality")]
        
        summary_data = [
            ["SPEED & MOTION", ""],
            ["Average Speed", f"{sum(speeds) / len(speeds):.2f} km/h" if speeds else "N/A"],
            ["Max Speed", f"{max(speeds):.2f} km/h" if speeds else "N/A"],
            ["Min Speed", f"{min(speeds):.2f} km/h" if speeds else "N/A"],
            ["", ""],
            ["TEMPERATURE (°C)", ""],
            ["Brake Temp", f"avg: {sum(brake_temps) / len(brake_temps):.1f}, max: {max(brake_temps):.1f}" if brake_temps else "N/A"],
            ["Transformer Temp", f"avg: {sum(transformer_temps) / len(transformer_temps):.1f}, max: {max(transformer_temps):.1f}" if transformer_temps else "N/A"],
            ["Converter Temp", f"avg: {sum(converter_temps) / len(converter_temps):.1f}, max: {max(converter_temps):.1f}" if converter_temps else "N/A"],
            ["Motor Temp", f"avg: {sum(motor_temps) / len(motor_temps):.1f}, max: {max(motor_temps):.1f}" if motor_temps else "N/A"],
            ["Axle Bearing Temp", f"avg: {sum(axle_temps) / len(axle_temps):.1f}, max: {max(axle_temps):.1f}" if axle_temps else "N/A"],
            ["", ""],
            ["PRESSURE (bar) / VOLTAGE", ""],
            ["Brake Cylinder Pressure", f"avg: {sum(brake_pressures) / len(brake_pressures):.2f}, max: {max(brake_pressures):.2f}" if brake_pressures else "N/A"],
            ["Brake Pipe Pressure", f"avg: {sum(brake_pipe_pressures) / len(brake_pipe_pressures):.2f}, max: {max(brake_pipe_pressures):.2f}" if brake_pipe_pressures else "N/A"],
            ["Pneumatic Pressure", f"avg: {sum(pneumatic_pressures) / len(pneumatic_pressures):.2f}, max: {max(pneumatic_pressures):.2f}" if pneumatic_pressures else "N/A"],
            ["Catenary Voltage (kV)", f"avg: {sum(catenary_voltages) / len(catenary_voltages):.2f}, min: {min(catenary_voltages):.2f}" if catenary_voltages else "N/A"],
            ["", ""],
            ["POWER & CURRENT", ""],
            ["Traction Current (A)", f"avg: {sum(traction_currents) / len(traction_currents):.1f}, max: {max(traction_currents):.1f}" if traction_currents else "N/A"],
            ["Traction Power (kW)", f"avg: {sum(traction_powers) / len(traction_powers):.1f}, max: {max(traction_powers):.1f}" if traction_powers else "N/A"],
            ["Regen Power (kW)", f"avg: {sum(regen_powers) / len(regen_powers):.1f}, max: {max(regen_powers):.1f}" if regen_powers else "N/A"],
            ["", ""],
            ["VIBRATION & MECHANICAL", ""],
            ["Motor Vibration", f"avg: {sum(vibration_motors) / len(vibration_motors):.2f}, max: {max(vibration_motors):.2f}" if vibration_motors else "N/A"],
            ["Gearbox Vibration", f"avg: {sum(vibration_gearboxes) / len(vibration_gearboxes):.2f}, max: {max(vibration_gearboxes):.2f}" if vibration_gearboxes else "N/A"],
            ["Compressor Cycles/hr", f"avg: {sum(compressor_cycles) / len(compressor_cycles):.1f}, max: {max(compressor_cycles):.1f}" if compressor_cycles else "N/A"],
            ["", ""],
            ["DATA QUALITY", ""],
            ["Signal Quality", f"avg: {sum(signal_qualities) / len(signal_qualities):.1f}%" if signal_qualities else "N/A"],
            ["Data Quality", f"avg: {sum(data_qualities) / len(data_qualities):.1f}%" if data_qualities else "N/A"],
            ["Total Events", str(len(events_data))],
            ["Report Generated", now.strftime("%Y-%m-%d %H:%M:%S UTC")],
            ["Time Range", f"{fifteen_min_ago.strftime('%H:%M:%S')} - {now.strftime('%H:%M:%S')} UTC"],
        ]
        
        summary_table = Table(summary_data, colWidths=[2.2 * inch, 2.3 * inch])
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
            ("BACKGROUND", (0, 4), (-1, 4), colors.HexColor("#f3f4f6")),
            ("BACKGROUND", (0, 12), (-1, 12), colors.HexColor("#f3f4f6")),
            ("BACKGROUND", (0, 20), (-1, 20), colors.HexColor("#f3f4f6")),
            ("BACKGROUND", (0, 26), (-1, 26), colors.HexColor("#f3f4f6")),
            ("BACKGROUND", (0, 31), (-1, 31), colors.HexColor("#f3f4f6")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
            ("TEXTCOLOR", (0, 4), (-1, 4), colors.HexColor("#1f2937")),
            ("TEXTCOLOR", (0, 12), (-1, 12), colors.HexColor("#1f2937")),
            ("TEXTCOLOR", (0, 20), (-1, 20), colors.HexColor("#1f2937")),
            ("TEXTCOLOR", (0, 26), (-1, 26), colors.HexColor("#1f2937")),
            ("TEXTCOLOR", (0, 31), (-1, 31), colors.HexColor("#1f2937")),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 4), (-1, 4), "Helvetica-Bold"),
            ("FONTNAME", (0, 12), (-1, 12), "Helvetica-Bold"),
            ("FONTNAME", (0, 20), (-1, 20), "Helvetica-Bold"),
            ("FONTNAME", (0, 26), (-1, 26), "Helvetica-Bold"),
            ("FONTNAME", (0, 31), (-1, 31), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#d1d5db")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.2 * inch))
        
        # Page break
        story.append(PageBreak())
        
        # Recent events table
        story.append(Paragraph("Recent Telemetry Events (Latest 20)", heading_style))
        story.append(Spacer(1, 0.1 * inch))
        
        events_table_data = [
            ["Time", "Speed", "Tractive\nEffort", "Brake Cyl\nPress", "Brake Temp", "Motor\nTemp", "Converter\nTemp", "Traction\nPower", "Vibration", "Signal"],
        ]
        
        for event in events_data[-20:]:  # Last 20 events
            timestamp_str = event.get("timestamp", "N/A")
            if timestamp_str != "N/A":
                timestamp_str = timestamp_str[-8:] if len(timestamp_str) > 8 else timestamp_str
            speed_str = f"{event.get('speed_kph', 0):.1f}" if event.get('speed_kph') else "N/A"
            effort_str = f"{event.get('tractive_effort_kn', 'N/A')}"
            brake_cyl_str = f"{event.get('brake_cylinder_pressure_bar', 'N/A')}"
            brake_temp_str = f"{event.get('brakes_temperature_c', 'N/A')}"
            motor_temp_str = f"{event.get('traction_motor_temp_c', 'N/A')}"
            converter_temp_str = f"{event.get('converter_temp_c', 'N/A')}"
            traction_power_str = f"{event.get('traction_power_kw', 'N/A')}"
            vibration_str = f"{event.get('vibration_motor', 'N/A')}"
            signal_str = f"{event.get('signal_quality', 'N/A')}"
            
            events_table_data.append([timestamp_str, speed_str, effort_str, brake_cyl_str, brake_temp_str, motor_temp_str, converter_temp_str, traction_power_str, vibration_str, signal_str])
        
        events_table = Table(events_table_data, colWidths=[0.9 * inch, 0.7 * inch, 0.75 * inch, 0.75 * inch, 0.75 * inch, 0.75 * inch, 0.75 * inch, 0.75 * inch, 0.75 * inch, 0.7 * inch])
        events_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
        ]))
        story.append(events_table)
        
        # Build PDF
        doc.build(story)
        pdf_buffer.seek(0)
        
        return StreamingResponse(
            iter([pdf_buffer.getvalue()]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={locomotive_id}_15min_report.pdf"},
        )
    except Exception as exc:
        logger.error(f"Error generating report for {locomotive_id}: {exc}")
        import traceback
        traceback.print_exc()
        return {"error": f"Failed to generate report: {str(exc)}"}, 500

