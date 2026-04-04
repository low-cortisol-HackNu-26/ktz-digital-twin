# Health Index computation engine.
#
# compute_health_index(packet: TelemetryPacket, config: ThresholdsConfig) -> HealthIndex
#
# Algorithm:
#   base_score = 100
#
#   For each parameter in config.parameters:
#     1. Normalize value to 0–1 using its normal range
#     2. If value in normal range: contribution = weight * 1.0
#     3. If value in warning range: contribution = weight * 0.5
#     4. If value in critical range: contribution = weight * 0.0
#     5. Apply penalty for each active alert matching this parameter
#     6. Accumulate: score += contribution * weight_factor
#
#   final_score = clamp(sum_of_contributions / total_weight * 100, 0, 100)
#
#   Determine grade from config.gradeThresholds (A/B/C/D/E)
#   Determine category from config.categoryThresholds (NORMAL/WARNING/CRITICAL)
#
#   Build top-5 factors sorted by |contribution - expected| descending
#
# Returns: HealthIndex with score, grade, category, factors, timestamp
