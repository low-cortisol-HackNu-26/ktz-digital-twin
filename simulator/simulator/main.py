from __future__ import annotations

import argparse
import asyncio
import logging
import os
from typing import Any
from urllib.parse import urlparse

import httpx

from .scenarios.highload import hz_for_scenario
from .state_machine import StateMachine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _parse_locomotives(value: str) -> list[str]:
	return [item.strip() for item in value.split(",") if item.strip()]


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
	hz: int,
) -> None:
	print(f"[{locomotive_id}] Starting, sending to {ingest_url}", flush=True)
	machine = StateMachine(locomotive_id=locomotive_id, scenario=scenario, hz=hz)
	sleep_time = 1.0 / max(1, hz)
	retry_sleep = 1.0

	async with httpx.AsyncClient(timeout=5.0) as client:
		while True:
			try:
				packet = machine.next_packet()
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
	parser.add_argument("--locos", default=os.getenv("LOCOS") or os.getenv("SIMULATOR_LOCOMOTIVE_ID") or "KZ8A-0001")
	parser.add_argument("--ingest-url", default=_derive_ingest_url())
	args = parser.parse_args()

	scenario = args.scenario.strip()
	locos = _parse_locomotives(args.locos)
	if not locos:
		locos = ["KZ8A-0001"]

	print(f"Starting simulator for {len(locos)} locos on route {scenario}", flush=True)
	hz = hz_for_scenario(args.hz, scenario)
	tasks = [
		_run_single_loco(args.ingest_url, loco_id, scenario, hz)
		for loco_id in locos
	]
	await asyncio.gather(*tasks)


if __name__ == "__main__":
	asyncio.run(_main())
