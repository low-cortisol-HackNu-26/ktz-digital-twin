# Anomaly scenario — injects realistic fault events to trigger alerts and degrade health index.
#
# class AnomalyScenario:
#   Extends NormalScenario base phases but injects fault events:
#
#   Event schedule (configurable, tick-based):
#     t=90s:   Oil pressure starts dropping slowly (LOW_OIL_PRESSURE warning at t=120s)
#     t=150s:  Engine temp spikes toward critical (ENG_OVERHEAT alert at t=180s)
#     t=200s:  Voltage fluctuation (HIGH_CURRENT alert)
#     t=240s:  Operator acknowledges ENG_OVERHEAT; temp begins recovering
#     t=300s:  Oil pressure recovers; all alerts resolve
#
#   update(state: dict, tick: int) -> dict
#     Applies fault injection on top of normal state updates
#     Injects alert codes into state["alerts"] list at trigger ticks
#
# Purpose: demonstrates health index degradation, alert panel behavior, and recovery
