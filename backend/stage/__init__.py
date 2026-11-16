"""Building stage classification and telecom priority scoring engine."""

from backend.stage.classifier import (
    classify_stage,
    estimate_completion_month,
    months_elapsed,
    parse_yyyymmdd,
    resolve_estimated_duration_months,
    resolve_near_completion_months,
)
from backend.stage.config import (
    AreaThreshold,
    DEFAULT_RULES_PATH,
    EstimatedDurationConfig,
    PriorityScoringConfig,
    ScoringWeights,
    StageClassificationConfig,
    StageRules,
    get_default_rules,
    load_rules,
)
from backend.stage.scorer import (
    calculate_priority_score,
    evaluate_building,
    score_households,
    score_main_purpose,
    score_stage,
    score_total_area,
)

__all__ = [
    "AreaThreshold",
    "DEFAULT_RULES_PATH",
    "EstimatedDurationConfig",
    "PriorityScoringConfig",
    "ScoringWeights",
    "StageClassificationConfig",
    "StageRules",
    "calculate_priority_score",
    "classify_stage",
    "estimate_completion_month",
    "evaluate_building",
    "get_default_rules",
    "load_rules",
    "months_elapsed",
    "parse_yyyymmdd",
    "resolve_estimated_duration_months",
    "resolve_near_completion_months",
    "score_households",
    "score_main_purpose",
    "score_stage",
    "score_total_area",
]
