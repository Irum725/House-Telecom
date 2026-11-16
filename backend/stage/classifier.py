"""Pure functions for classifying a building into BuildingStage."""

from datetime import date, datetime
import re
from typing import Any, Mapping, Optional

from backend.stage.config import StageRules, get_default_rules
from shared.enums import BuildingStage

_DIGITS_8_RE = re.compile(r"^\d{8}$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_yyyymmdd(value: str | date | datetime | None) -> Optional[date]:
    """Parse a 건축HUB YYYYMMDD string (or ISO date/date/datetime) into a date.

    Returns None for empty, whitespace-only, all-zero, or malformed values.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text or text == "00000000":
        return None

    if _DIGITS_8_RE.match(text):
        year, month, day = int(text[:4]), int(text[4:6]), int(text[6:8])
    elif _ISO_DATE_RE.match(text):
        year, month, day = int(text[:4]), int(text[5:7]), int(text[8:10])
    else:
        return None

    try:
        return date(year, month, day)
    except ValueError:
        return None


def months_elapsed(start: date, end: date) -> int:
    """Return whole calendar months elapsed from `start` to `end` (minimum 0)."""
    if end <= start:
        return 0
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(0, months)


def _match_area_months(
    tot_area: Optional[float],
    thresholds: list,
    default_months: int,
    use_area_adjustment: bool = True,
) -> int:
    if not use_area_adjustment or tot_area is None or tot_area < 0 or not thresholds:
        return default_months

    for threshold in thresholds:
        if threshold.max_tot_area is None or tot_area < threshold.max_tot_area:
            return threshold.months

    return default_months


def resolve_near_completion_months(
    tot_area: Optional[float] = None,
    rules: Optional[StageRules] = None,
) -> int:
    """Determine the NEAR_COMPLETION month threshold, optionally adjusted by tot_area."""
    active_rules = rules or get_default_rules()
    cfg = active_rules.stage_classification
    return _match_area_months(
        tot_area=tot_area,
        thresholds=cfg.area_thresholds,
        default_months=cfg.default_near_completion_months,
        use_area_adjustment=cfg.use_area_adjustment,
    )


def resolve_estimated_duration_months(
    tot_area: Optional[float] = None,
    rules: Optional[StageRules] = None,
) -> int:
    """Determine estimated construction duration in months, adjusted by tot_area."""
    active_rules = rules or get_default_rules()
    dur_cfg = active_rules.stage_classification.estimated_duration_months
    return _match_area_months(
        tot_area=tot_area,
        thresholds=dur_cfg.area_thresholds,
        default_months=dur_cfg.default_months,
        use_area_adjustment=True,
    )


def classify_stage(
    use_apr_day: str | date | datetime | None = None,
    real_stcns_day: str | date | datetime | None = None,
    stcns_sched_day: str | date | datetime | None = None,
    arch_pms_day: str | date | datetime | None = None,
    tot_area: Optional[float] = None,
    *,
    reference_date: Optional[date] = None,
    rules: Optional[StageRules] = None,
    near_completion_months: Optional[int] = None,
) -> BuildingStage:
    """Classify a building's lifecycle stage from its permit/construction dates.

    Precedence:
    1. USE_APPROVED: valid use_apr_day present.
    2. NEAR_COMPLETION: valid real_stcns_day present and elapsed months >= threshold.
    3. UNDER_CONSTRUCTION: valid real_stcns_day present (elapsed < threshold).
    4. START_SCHEDULED: valid stcns_sched_day present.
    5. PERMITTED: valid arch_pms_day present (or default initial stage).
    """
    if parse_yyyymmdd(use_apr_day) is not None:
        return BuildingStage.USE_APPROVED

    real_start = parse_yyyymmdd(real_stcns_day)
    if real_start is not None:
        ref = reference_date or date.today()
        threshold = (
            near_completion_months
            if near_completion_months is not None
            else resolve_near_completion_months(tot_area=tot_area, rules=rules)
        )
        if months_elapsed(real_start, ref) >= threshold:
            return BuildingStage.NEAR_COMPLETION
        return BuildingStage.UNDER_CONSTRUCTION

    if parse_yyyymmdd(stcns_sched_day) is not None:
        return BuildingStage.START_SCHEDULED

    # arch_pms_day present or fallback default initial stage
    return BuildingStage.PERMITTED


def estimate_completion_month(
    real_stcns_day: str | date | datetime | None = None,
    stcns_sched_day: str | date | datetime | None = None,
    use_apr_day: str | date | datetime | None = None,
    tot_area: Optional[float] = None,
    rules: Optional[StageRules] = None,
) -> Optional[str]:
    """Estimate completion month ('YYYY-MM') from start date + area-based duration.

    Returns None when use_apr_day is already set or when neither real_stcns_day
    nor stcns_sched_day is a valid date.
    """
    if parse_yyyymmdd(use_apr_day) is not None:
        return None

    start_date = parse_yyyymmdd(real_stcns_day) or parse_yyyymmdd(stcns_sched_day)
    if start_date is None:
        return None

    months = resolve_estimated_duration_months(tot_area=tot_area, rules=rules)
    total_months = (start_date.year * 12 + (start_date.month - 1)) + max(0, months)
    target_year = total_months // 12
    target_month = (total_months % 12) + 1
    return f"{target_year:04d}-{target_month:02d}"
