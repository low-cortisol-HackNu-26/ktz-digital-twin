# Normal operating scenario — locomotive accelerates, cruises, and decelerates.
#
# class NormalScenario:
#   Phases (by tick ranges):
#     0–60s:    Startup — engine warms up, idle speed, temperature rising
#     60–120s:  Acceleration — throttle increases, speed ramps to 80 km/h
#     120–600s: Cruise — steady 80 km/h, slight parameter drift
#     600–660s: Deceleration — throttle off, brakes apply, speed → 0
#     660+:     Idle — repeat or loop
#
#   update(state: dict, tick: int) -> dict
#     Returns updated state dict for current tick
#     All parameters stay within normal thresholds
#     Fuel decreases at realistic rate (≈50 L/h at cruise)
