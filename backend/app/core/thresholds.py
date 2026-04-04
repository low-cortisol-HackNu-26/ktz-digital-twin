# ThresholdsConfig singleton — loads and hot-reloads thresholds.json.
#
# class ThresholdsConfig:
#   Pydantic model mirroring the structure in shared/thresholds.json:
#     parameters: dict[str, ParameterThreshold]
#     gradeThresholds: dict[str, float]
#     categoryThresholds: dict[str, float]
#
# class ParameterThreshold:
#   weight: float
#   normal: RangeSpec
#   warning: RangeSpec
#   critical: RangeSpec
#   penaltyPerAlert: float
#
# class RangeSpec:
#   min: float
#   max: float
#
# load_thresholds(path: str) -> ThresholdsConfig
#   Reads JSON file, validates with Pydantic, returns instance.
#   Called on startup and on PUT /api/thresholds.
#
# _config: ThresholdsConfig | None = None  (module-level cache)
# get_thresholds() -> ThresholdsConfig     (returns cached, raises if not loaded)
# reload_thresholds(path: str) -> ThresholdsConfig
