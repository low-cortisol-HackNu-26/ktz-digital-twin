# Locomotive state machine — generates realistic telemetry over time.
#
# class StateMachine:
#   __init__(locomotive_id: str, scenario: str = "normal")
#     Loads the appropriate scenario module (normal/anomaly/highload)
#     Initializes internal state: speed, fuel, temps, etc. at realistic starting values
#
#   next_packet() -> TelemetryPacket
#     Advances the state by one tick:
#       1. Delegates state update to current scenario
#       2. Adds Gaussian noise to numeric fields (numpy)
#       3. Checks scenario-defined event triggers (e.g. at t=120s, inject overheat)
#       4. Builds and returns a TelemetryPacket with current state
#
#   tick: int  (incremented each call, used for scenario timing)
#   current_scenario: BaseScenario
#
# State transitions:
#   The machine can switch scenario mid-run (e.g. normal → anomaly at a threshold)
#   allowing for realistic degradation simulation.
