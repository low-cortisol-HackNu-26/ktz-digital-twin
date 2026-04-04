# Integration tests for WebSocket endpoints.
#
# Uses FastAPI TestClient with websocket_connect context manager.
#
# test_ws_requires_valid_token:
#   Connect without token → connection closed with code 4001
#
# test_ws_receives_telemetry_on_ingest:
#   1. Connect client to /ws/telemetry/LOC-001
#   2. POST a telemetry packet to /ws/ingest/LOC-001 (or via simulator mock)
#   3. Client receives JSON message with TelemetryPacketWithHealthSchema shape
#
# test_ws_broadcast_to_multiple_clients:
#   Connect 3 clients to same locomotiveId → all receive each ingest
#
# test_ws_reconnect_sends_latest_state:
#   Ingest a packet, disconnect client, reconnect → receives "hello" with latest
