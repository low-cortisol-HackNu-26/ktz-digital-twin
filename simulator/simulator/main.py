# Simulator entry point.
#
# asyncio main loop:
#   1. Read config from env (TARGET_WS, LOCOMOTIVE_ID, HZ, SCENARIO)
#   2. Instantiate StateMachine with chosen scenario
#   3. Connect to backend /ws/ingest/{locomotiveId} via websockets.connect()
#      with reconnect loop (exponential backoff, max 60s)
#   4. Every 1/HZ seconds:
#        packet = state_machine.next_packet()
#        await ws.send(packet.model_dump_json())
#   5. Handle KeyboardInterrupt gracefully (log "Simulator stopped")
#
# CLI override: python -m simulator.main --scenario=highload --hz=10
