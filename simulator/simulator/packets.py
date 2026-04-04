# Packet builder helpers for the simulator.
#
# build_packet(locomotive_id: str, state: dict) -> dict
#   Constructs a dict matching TelemetryPacket shape (shared/types/telemetry.ts)
#   Fills timestamp with current Unix ms
#   Maps internal state field names to protocol field names
#   Returns raw dict (serialized to JSON by main loop)
#
# FIELD_NOISE: dict[str, float]
#   Per-field standard deviation for Gaussian noise injection
#   e.g. speed: 0.5, engineTemp: 0.3, voltage: 2.0
#
# DEFAULT_INITIAL_STATE: dict
#   Starting values for a stationary locomotive:
#   speed=0, throttle=0, fuelLevel=2000, engineTemp=20, ...
