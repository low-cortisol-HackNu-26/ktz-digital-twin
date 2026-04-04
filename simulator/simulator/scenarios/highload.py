# Highload scenario — sends packets at 10x normal rate to stress-test the system.
#
# class HighloadScenario:
#   Same state logic as NormalScenario but:
#     - Designed to run at 10 Hz (set SIMULATOR_HZ=10)
#     - Generates multiple locomotives simultaneously if SIMULATOR_MULTI_LOCO=true
#       (forks separate asyncio tasks for LOC-001 through LOC-010)
#     - Each locomotive has slightly different state/phase offset to simulate fleet
#
#   Purpose: demonstrate system handles x10 event burst without UI lag
#   Expected: backend processes without queuing, frontend renders < 500ms
#
# Use with: docker compose run simulator --scenario=highload --hz=10
