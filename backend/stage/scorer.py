"""Pure functions for calculating telecom sales priority score (0-100)."""

from datetime import date, datetime
from typing import Any, Mapping, Optional

from backend.stage.classifier import classify_stage
from backend.stage.config import PriorityScoringConfig, ScoringWeights, StageRules, get_default_rules
from shared.enums import BuildingStage


def _interpolate_brackets(value: Optional[float], brackets: list[tuple[float, float]]) -> float:
    """Piecewise linear interpolation over sorted (x, y) brackets, clamped to [0, 100]."""
    if value is None or value <= 0 or not brackets:
        return 0.0

    if value <= brackets[0][0]:
        return max(0.0, min(100.0, float(brackets[0][1])))

    for idx in range(1, len(brackets)):
        x0, y0 = brackets[idx - 1]
        x1, y1 = brackets[idx]
        if value <= x1:
            if x1 == x0:
                return max(0.0, min(100.0, float(y1)))
            ratio = (value - x0) / (x1 - x0)
            score = y0 + ratio * (y1 - y0)
            return max(0.0, min(100.0, float(score)))

    return max(0.0, min(100.0, float(brackets[-1][1])))


def score_households(
    hhld_cnt: Optional[int],
    config: Optional[PriorityScoringConfig] = None,
) -> float:
    """Return 0-100 sub-score for household count (세대수)."""
    cfg = config or get_default_rules().priority_scoring
    val = float(hhld_cnt) if hhld_cnt is not None else None
    return _interpolate_brackets(val, cfg.hhld_cnt_brackets)


def score_total_area(
    tot_area: Optional[float],
    config: Optional[PriorityScoringConfig] = None,
) -> float:
    """Return 0-100 sub-score for total floor area in ㎡ (연면적)."""
    cfg = config or get_default_rules().priority_scoring
    return _interpolate_brackets(tot_area, cfg.tot_area_brackets)


def score_main_purpose(
    main_purps_cd_nm: Optional[str],
    config: Optional[PriorityScoringConfig] = None,
) -> float:
    """Return 0-100 sub-score for building main purpose (주용도)."""
    cfg = config or get_default_rules().priority_scoring
    if main_purps_cd_nm is None:
        return cfg.empty_purpose_score

    text = main_purps_cd_nm.strip()
    if not text:
        return cfg.empty_purpose_score

    if text in cfg.purpose_scores:
        return float(cfg.purpose_scores[text])

    # Match longest keyword substring first (e.g. '제2종근린생활시설' before '근린생활시설')
    for keyword in sorted(cfg.purpose_scores.keys(), key=len, reverse=True):
        if keyword in text:
            return float(cfg.purpose_scores[keyword])

    return cfg.default_purpose_score


def score_stage(
    stage: BuildingStage | str,
    config: Optional[PriorityScoringConfig] = None,
) -> float:
    """Return 0-100 sub-score for building stage / completion urgency (준공 임박도)."""
    cfg = config or get_default_rules().priority_scoring
    key = stage.value if isinstance(stage, BuildingStage) else str(stage).strip()
    return float(cfg.stage_scores.get(key, 0.0))


def calculate_priority_score(
    hhld_cnt: Optional[int] = None,
    tot_area: Optional[float] = None,
    main_purps_cd_nm: Optional[str] = None,
    stage: BuildingStage | str = BuildingStage.PERMITTED,
    *,
    rules: Optional[StageRules] = None,
    weights: Optional[ScoringWeights] = None,
) -> float:
    """Calculate weighted telecom priority score in [0.0, 100.0]."""
    cfg = (rules or get_default_rules()).priority_scoring
    active_weights = weights or cfg.weights
    total_weight = active_weights.total
    if total_weight <= 0:
        return 0.0

    raw_score = (
        active_weights.hhld_cnt * score_households(hhld_cnt, cfg)
        + active_weights.tot_area * score_total_area(tot_area, cfg)
        + active_weights.main_purps * score_main_purpose(main_purps_cd_nm, cfg)
        + active_weights.stage * score_stage(stage, cfg)
    ) / total_weight

    return round(max(0.0, min(100.0, raw_score)), 2)


def _get_field(obj: Any, key: str) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key)
    return getattr(obj, key, None)


def evaluate_building(
    building: Any,
    *,
    reference_date: Optional[date] = None,
    rules: Optional[StageRules] = None,
    weights: Optional[ScoringWeights] = None,
    near_completion_months: Optional[int] = None,
) -> tuple[BuildingStage, float]:
    """Classify stage and calculate priority score for a Building ORM model or dict."""
    tot_area = _get_field(building, "tot_area")
    stage = classify_stage(
        use_apr_day=_get_field(building, "use_apr_day"),
        real_stcns_day=_get_field(building, "real_stcns_day"),
        stcns_sched_day=_get_field(building, "stcns_sched_day"),
        arch_pms_day=_get_field(building, "arch_pms_day"),
        tot_area=tot_area,
        reference_date=reference_date,
        rules=rules,
        near_completion_months=near_completion_months,
    )
    score = calculate_priority_score(
        hhld_cnt=_get_field(building, "hhld_cnt"),
        tot_area=tot_area,
        main_purps_cd_nm=_get_field(building, "main_purps_cd_nm"),
        stage=stage,
        rules=rules,
        weights=weights,
    )
    return stage, score
