from __future__ import annotations

import argparse
import asyncio
import logging
import os
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from .scenarios.highload import hz_for_scenario
from .state_machine import StateMachine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _parse_locomotives(value: str) -> list[str]:
	return [item.strip() for item in value.split(",") if item.strip()]


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
	if value is None:
		return default
	return value.strip().lower() in {"1", "true", "yes", "on"}


def _derive_ingest_url() -> str:
	explicit = os.getenv("INGEST_URL") or os.getenv("SIMULATOR_INGEST_URL")
	if explicit:
		return explicit

	ws_target = os.getenv("WS_TARGET") or os.getenv("SIMULATOR_TARGET_WS")
	if ws_target:
		parsed = urlparse(ws_target)
		scheme = "https" if parsed.scheme == "wss" else "http"
		host = parsed.netloc or "backend:8000"
		return f"{scheme}://{host}/api/ingest/telemetry"

	return "http://backend:8000/api/ingest/telemetry"


async def _post_event(client: httpx.AsyncClient, ingest_url: str, event: dict[str, Any]) -> None:
	response = await client.post(ingest_url, json=event)
	response.raise_for_status()


async def _run_single_loco(
	ingest_url: str,
	locomotive_id: str,
	scenario: str,
	baseline_hz: int,
	highload_enabled: bool,
	highload_start_seconds: float,
	highload_duration_seconds: float,
	burst_multiplier: int,
	simulation_started_at: float,
) -> None:
	print(f"[{locomotive_id}] Starting, sending to {ingest_url}", flush=True)
	bucket_hz = max(1, baseline_hz * max(1, burst_multiplier))
	machine = StateMachine(locomotive_id=locomotive_id, scenario=scenario, hz=bucket_hz)
	retry_sleep = 1.0
	last_mode: str | None = None

	def _current_load(elapsed_seconds: float) -> tuple[str, bool, int]:
		if not highload_enabled:
			return "normal", False, 1
		in_burst = highload_start_seconds <= elapsed_seconds < (highload_start_seconds + highload_duration_seconds)
		if in_burst:
			return "highload_x10", True, max(1, burst_multiplier)
		return "normal", False, 1

	async with httpx.AsyncClient(timeout=5.0) as client:
		while True:
			elapsed_seconds = max(0.0, time.monotonic() - simulation_started_at)
			load_mode, burst_active, effective_multiplier = _current_load(elapsed_seconds)
			effective_hz = max(1, baseline_hz * effective_multiplier)
			sleep_time = 1.0 / effective_hz
			if load_mode != last_mode:
				logger.info(
					"[%s] load mode changed: %s (hz=%s, elapsed=%.1fs)",
					locomotive_id,
					load_mode,
					effective_hz,
					elapsed_seconds,
				)
				last_mode = load_mode

			try:
				packet = machine.next_packet()
				packet["load_mode"] = load_mode
				packet["burst_active"] = burst_active
				packet["burst_multiplier"] = effective_multiplier
				await _post_event(client, ingest_url, packet)
				retry_sleep = 1.0
			except httpx.ConnectError as e:
				logger.warning("POST connection error for %s: %s", locomotive_id, e)
				await asyncio.sleep(retry_sleep)
				retry_sleep = min(30.0, retry_sleep * 2.0)
				continue
			except Exception as e:
				logger.warning("POST failed for %s: %s", locomotive_id, e)
				await asyncio.sleep(retry_sleep)
				retry_sleep = min(30.0, retry_sleep * 2.0)
				continue

			await asyncio.sleep(sleep_time)


async def _main() -> None:
	parser = argparse.ArgumentParser(description="KZ8A telemetry simulator")
	parser.add_argument("--scenario", default=os.getenv("SCENARIO") or os.getenv("SIMULATOR_SCENARIO") or "normal")
	parser.add_argument("--hz", type=int, default=int(os.getenv("HZ") or os.getenv("SIMULATOR_HZ") or "5"))
	parser.add_argument("--baseline-rate", type=int, default=int(os.getenv("BASELINE_RATE") or "0"))
	parser.add_argument("--highload-x10", default=os.getenv("HIGHLOAD_X10") or "false")
	parser.add_argument("--highload-start-seconds", type=float, default=float(os.getenv("HIGHLOAD_START_SECONDS") or "10"))
	parser.add_argument("--highload-duration-seconds", type=float, default=float(os.getenv("HIGHLOAD_DURATION_SECONDS") or "10"))
	parser.add_argument("--burst-multiplier", type=int, default=int(os.getenv("BURST_MULTIPLIER") or "10"))
	parser.add_argument("--locos", default=os.getenv("LOCOS") or os.getenv("SIMULATOR_LOCOMOTIVE_ID") or "KZ8A-0001")
	parser.add_argument("--ingest-url", default=_derive_ingest_url())
	args = parser.parse_args()

	scenario = args.scenario.strip()
	locos = _parse_locomotives(args.locos)
	if not locos:
		locos = ["KZ8A-0001"]

	print(f"Starting simulator for {len(locos)} locos on route {scenario}", flush=True)
	base_hz = hz_for_scenario(args.hz, scenario)
	if args.baseline_rate > 0:
		base_hz = max(1, args.baseline_rate)

	highload_enabled = _parse_bool(args.highload_x10, default=False) or scenario == "highload_x10"
	highload_start_seconds = max(0.0, args.highload_start_seconds)
	highload_duration_seconds = max(0.0, args.highload_duration_seconds)
	burst_multiplier = max(1, args.burst_multiplier)
	simulation_started_at = time.monotonic()

	tasks = [
		_run_single_loco(
			args.ingest_url,
			loco_id,
			scenario,
			base_hz,
			highload_enabled,
			highload_start_seconds,
			highload_duration_seconds,
			burst_multiplier,
			simulation_started_at,
		)
		for loco_id in locos
	]
	await asyncio.gather(*tasks)


if __name__ == "__main__":
	asyncio.run(_main())
