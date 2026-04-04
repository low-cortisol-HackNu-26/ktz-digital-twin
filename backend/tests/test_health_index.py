# Unit tests for the Health Index computation (core/health_index.py).
#
# Test cases to cover:
#
# test_perfect_packet_scores_100:
#   All parameters in normal range → score == 100, grade == "A"
#
# test_critical_engine_temp_lowers_score:
#   engineTemp in critical range → score < 45, grade == "E" or "D", category == "CRITICAL"
#
# test_multiple_warnings_degrade_grade:
#   3 parameters in warning range → grade in ["C","D"]
#
# test_alert_penalty_applied:
#   ENG_OVERHEAT alert in packet → score lower than same packet without alert
#
# test_top_5_factors_returned:
#   result.factors has at most 5 entries, sorted by |contribution| desc
#
# test_weights_sum_respected:
#   custom thresholds with sum(weights) != 1 → score still in 0–100 range (normalized)
