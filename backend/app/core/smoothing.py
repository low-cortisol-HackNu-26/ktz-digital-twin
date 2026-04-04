# Signal processing for incoming telemetry packets.
#
# class EMAsmoother:
#   __init__(alpha: float = 0.2)
#     alpha: smoothing factor (0=fully smoothed, 1=no smoothing)
#   smooth(field: str, value: float) -> float
#     Returns EMA-smoothed value; initializes with first value
#   reset(): clears all state (e.g., on locomotive reconnect)
#
# Smoothed fields: speed, engineTemp, oilPressure, brakePressure, voltage, current,
#   fuelConsumptionRate (not fuelLevel — tank level doesn't need smoothing)
#
# validate_packet(packet: TelemetryPacketSchema) -> TelemetryPacketSchema | None
#   Returns None if packet fails sanity checks:
#     - timestamp is not more than 10s in the future
#     - speed is 0–350 km/h
#     - engineTemp is -50–500°C
#     - voltage is 0–5000V
#   Otherwise returns the validated packet (with out-of-range fields clamped and logged)
