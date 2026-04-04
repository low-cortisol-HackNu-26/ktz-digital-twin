"""
Seed test data: creates locomotives with assigned operators and sample telemetry.

Uses the simulator data format for consistency.
Creates:
  1. Multiple locomotives (from simulator scenarios)
  2. Multiple operators (admin + drivers)
  3. Associates drivers with locomotives for map testing

Usage (from backend/ with venv active):
    python seed_test_data.py
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.session import Base
from app.models import DriverAccount, Locomotive, LocomotivePosition, TelemetryEventRecord

# PBKDF2 password hashing (matches auth.py)
PBKDF2_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 390_000
SALT_BYTES = 16


def _pbkdf2_digest(password: str, salt: bytes, iterations: int) -> str:
	dk = hashlib.pbkdf2_hmac(
		"sha256", password.encode("utf-8"), salt, iterations)
	return dk.hex()


def _hash_password(plain_password: str) -> str:
	salt = secrets.token_bytes(SALT_BYTES)
	digest = _pbkdf2_digest(plain_password, salt, PBKDF2_ITERATIONS)
	return f"{PBKDF2_ALGORITHM}${PBKDF2_ITERATIONS}${salt.hex()}${digest}"


def utcnow() -> datetime:
	return datetime.now(timezone.utc)


# Simulator locomotive IDs (from simulator/main.py default)
LOCOMOTIVES = [
	{
		"id": "LK-41",
		"display_name": "KZ8A-0041 (Almaty–Nur-Sultan)",
		"gps_lat": 43.2389,
		"gps_lon": 76.8897,
		"route_code": "ALA-NUR",
	},
	{
		"id": "LK-42",
		"display_name": "KZ8A-0042 (Almaty–Shymkent)",
		"gps_lat": 42.3167,
		"gps_lon": 69.5900,
		"route_code": "ALA-SHY",
	},
	{
		"id": "LK-43",
		"display_name": "KZ8A-0043 (Nur-Sultan–Aktobe)",
		"gps_lat": 51.1801,
		"gps_lon": 71.4460,
		"route_code": "NUR-AKT",
	},
]

# Test operators
OPERATORS = [
	{
		"company_id": "ADMIN-001",
		"name": "Admin User",
		"password": "admin123",
		"role": "Admin",
		"locomotive_id": None,
	},
	{
		"company_id": "DRV-001",
		"name": "Driver 1",
		"password": "driver123",
		"role": "Driver",
		"locomotive_id": "LK-41",
	},
	{
		"company_id": "DRV-002",
		"name": "Driver 2",
		"password": "driver456",
		"role": "Driver",
		"locomotive_id": "LK-42",
	},
	{
		"company_id": "DRV-003",
		"name": "Driver 3",
		"password": "driver789",
		"role": "Driver",
		"locomotive_id": "LK-43",
	},
]

# Sample telemetry events (simulator-compatible format)
def _sample_telemetry(locomotive_id: str, gps_lat: float, gps_lon: float) -> dict:
	return {
		"timestamp": datetime.now(timezone.utc).isoformat(),
		"locomotive_id": locomotive_id,
		"speed_kph": 60.0,
		"target_speed_kph": 80.0,
		"allowed_speed_kph": 100.0,
		"acceleration": 0.5,
		"traction_mode": "power",
		"tractive_effort_kn": 200.0,
		"brake_pipe_pressure_bar": 5.0,
		"brake_cylinder_pressure_bar": 0.0,
		"pantograph_up": True,
		"catenary_voltage_kv": 25.0,
		"traction_current_a": 450.0,
		"traction_power_kw": 2500.0,
		"regen_power_kw": 0.0,
		"transformer_temp_c": 55.0,
		"converter_temp_c": 48.0,
		"traction_motor_temp_c": 62.0,
		"axle_bearing_temp_c": 42.0,
		"compressor_state": "on",
		"compressor_cycles_per_hour": 9.5,
		"pneumatic_pressure_bar": 7.8,
		"vibration_motor": 0.8,
		"vibration_gearbox": 0.7,
		"gps_lat": gps_lat,
		"gps_lon": gps_lon,
		"route_segment": "TEST:000",
		"gradient_permille": 2.5,
		"train_mass_tons": 6500.0,
		"active_fault_codes": [],
		"signal_quality": 0.98,
		"data_quality": 0.99,
		"source": "simulator",
		"schema_version": "1.0",
	}


async def seed_data() -> None:
	"""Create locomotives and operators in database."""
	engine = create_async_engine(settings.DATABASE_URL, echo=False)

	# Create tables
	async with engine.begin() as conn:
		await conn.run_sync(Base.metadata.create_all)

	AsyncSessionLocal = async_sessionmaker(
		bind=engine,
		expire_on_commit=False,
		class_=AsyncSession,
	)

	async with AsyncSessionLocal() as session:
		# Create locomotives
		for loco_data in LOCOMOTIVES:
			existing = await session.execute(
				select(Locomotive).where(
					Locomotive.id == loco_data["id"]
				)
			)
			if existing.scalar_one_or_none() is None:
				locomotive = Locomotive(
					id=loco_data["id"],
					display_name=loco_data["display_name"],
				)
				session.add(locomotive)
				print(f"✓ Created locomotive: {loco_data['id']}")
			else:
				print(f"⊘ Locomotive already exists: {loco_data['id']}")

		# Create operators
		for op_data in OPERATORS:
			existing = await session.execute(
				select(DriverAccount).where(
					DriverAccount.company_id == op_data["company_id"]
				)
			)
			if existing.scalar_one_or_none() is None:
				operator = DriverAccount(
					company_id=op_data["company_id"],
					password_hash=_hash_password(op_data["password"]),
					name=op_data["name"],
					role=op_data["role"],
					locomotive_id=op_data["locomotive_id"],
					is_active=True,
				)
				session.add(operator)
				print(
					f"✓ Created {op_data['role']}: {op_data['company_id']} "
					f"(loco: {op_data['locomotive_id'] or 'none'})"
				)
			else:
				print(f"⊘ Operator already exists: {op_data['company_id']}")

		await session.commit()

		# Create locomotive positions for map display
		for loco_data in LOCOMOTIVES:
			loco_id = loco_data["id"]
			position = LocomotivePosition(
				locomotive_id=loco_id,
				lat=loco_data["gps_lat"],
				lng=loco_data["gps_lon"],
				speed=60.0,
				heading=180.0,
				route_code=loco_data["route_code"],
				snapped_lat=loco_data["gps_lat"],
				snapped_lng=loco_data["gps_lon"],
				distance_to_route_m=0.0,
				progress_pct=25.0,
			)
			session.add(position)
			print(f"✓ Created position for: {loco_id}")

		await session.commit()

		for loco_data in LOCOMOTIVES:
			loco_id = loco_data["id"]
			telemetry_data = _sample_telemetry(
				loco_id, loco_data["gps_lat"], loco_data["gps_lon"]
			)
			telemetry = TelemetryEventRecord(
				locomotive_id=loco_id,
				timestamp=utcnow(),
				speed_kph=telemetry_data.get("speed_kph", 0.0),
				target_speed_kph=telemetry_data.get("target_speed_kph"),
				allowed_speed_kph=telemetry_data.get("allowed_speed_kph"),
				acceleration=telemetry_data.get("acceleration"),
				traction_mode=telemetry_data.get("traction_mode", "coast"),
				tractive_effort_kn=telemetry_data.get("tractive_effort_kn"),
				brake_pipe_pressure_bar=telemetry_data.get("brake_pipe_pressure_bar"),
				brake_cylinder_pressure_bar=telemetry_data.get("brake_cylinder_pressure_bar"),
				pantograph_up=telemetry_data.get("pantograph_up", True),
				catenary_voltage_kv=telemetry_data.get("catenary_voltage_kv"),
				traction_current_a=telemetry_data.get("traction_current_a"),
				traction_power_kw=telemetry_data.get("traction_power_kw"),
				regen_power_kw=telemetry_data.get("regen_power_kw"),
				transformer_temp_c=telemetry_data.get("transformer_temp_c"),
				converter_temp_c=telemetry_data.get("converter_temp_c"),
				traction_motor_temp_c=telemetry_data.get("traction_motor_temp_c"),
				axle_bearing_temp_c=telemetry_data.get("axle_bearing_temp_c"),
				compressor_state=telemetry_data.get("compressor_state"),
				compressor_cycles_per_hour=telemetry_data.get("compressor_cycles_per_hour"),
				pneumatic_pressure_bar=telemetry_data.get("pneumatic_pressure_bar"),
				vibration_motor=telemetry_data.get("vibration_motor"),
				vibration_gearbox=telemetry_data.get("vibration_gearbox"),
				gps_lat=telemetry_data.get("gps_lat"),
				gps_lon=telemetry_data.get("gps_lon"),
				route_segment=telemetry_data.get("route_segment"),
				gradient_permille=telemetry_data.get("gradient_permille"),
				train_mass_tons=telemetry_data.get("train_mass_tons"),
				active_fault_codes=telemetry_data.get("active_fault_codes", []),
				signal_quality=telemetry_data.get("signal_quality"),
				data_quality=telemetry_data.get("data_quality"),
				source=telemetry_data.get("source"),
				schema_version=telemetry_data.get("schema_version"),
			)
			session.add(telemetry)
			print(f"✓ Created sample telemetry for: {loco_id}")

		await session.commit()

	await engine.dispose()
	print("\n✅ Seeding complete!")
	print("\nTest credentials:")
	for op in OPERATORS:
		print(f"  {op['company_id']:12} / {op['password']:12} ({op['role']})")


if __name__ == "__main__":
	asyncio.run(seed_data())
