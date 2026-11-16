"""Configuration loader and Pydantic schemas for building stage & priority rules."""

from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator


DEFAULT_RULES_PATH = Path(__file__).resolve().parent / "rules.yaml"


class AreaThreshold(BaseModel):
    """Maps an upper bound on tot_area (㎡) to the required elapsed months."""

    max_tot_area: Optional[float] = Field(
        default=None,
        description="Exclusive upper bound for tot_area; None means unbounded.",
    )
    months: int = Field(ge=0, description="Months from real_stcns_day to NEAR_COMPLETION.")


class EstimatedDurationConfig(BaseModel):
    """Rules for estimated total construction duration (months) by tot_area."""

    default_months: int = Field(default=14, ge=0)
    area_thresholds: list[AreaThreshold] = Field(default_factory=list)


class StageClassificationConfig(BaseModel):
    """Rules controlling how a building is classified into BuildingStage."""

    default_near_completion_months: int = Field(default=12, ge=0)
    use_area_adjustment: bool = Field(default=True)
    area_thresholds: list[AreaThreshold] = Field(default_factory=list)
    estimated_duration_months: EstimatedDurationConfig = Field(
        default_factory=EstimatedDurationConfig
    )


class ScoringWeights(BaseModel):
    """Relative weights for each priority scoring dimension."""

    hhld_cnt: float = Field(default=0.35, ge=0.0)
    tot_area: float = Field(default=0.25, ge=0.0)
    main_purps: float = Field(default=0.20, ge=0.0)
    stage: float = Field(default=0.20, ge=0.0)

    @property
    def total(self) -> float:
        return self.hhld_cnt + self.tot_area + self.main_purps + self.stage


class PriorityScoringConfig(BaseModel):
    """Rules controlling telecom sales priority scoring (0-100)."""

    weights: ScoringWeights = Field(default_factory=ScoringWeights)
    hhld_cnt_brackets: list[tuple[float, float]] = Field(default_factory=list)
    tot_area_brackets: list[tuple[float, float]] = Field(default_factory=list)
    purpose_scores: dict[str, float] = Field(default_factory=dict)
    default_purpose_score: float = Field(default=40.0, ge=0.0, le=100.0)
    empty_purpose_score: float = Field(default=20.0, ge=0.0, le=100.0)
    stage_scores: dict[str, float] = Field(default_factory=dict)

    @field_validator("hhld_cnt_brackets", "tot_area_brackets")
    @classmethod
    def _validate_brackets(
        cls, value: list[tuple[float, float]]
    ) -> list[tuple[float, float]]:
        return sorted(value, key=lambda pair: pair[0])


class StageRules(BaseModel):
    """Top-level configuration container for stage classification and priority scoring."""

    stage_classification: StageClassificationConfig = Field(
        default_factory=StageClassificationConfig
    )
    priority_scoring: PriorityScoringConfig = Field(
        default_factory=PriorityScoringConfig
    )


def load_rules(path: Optional[str | Path] = None) -> StageRules:
    """Load and validate stage rules from a YAML file."""
    target = Path(path) if path is not None else DEFAULT_RULES_PATH
    with target.open("r", encoding="utf-8") as fp:
        raw = yaml.safe_load(fp) or {}
    return StageRules.model_validate(raw)


@lru_cache(maxsize=1)
def get_default_rules() -> StageRules:
    """Return cached default StageRules loaded from backend/stage/rules.yaml."""
    return load_rules(DEFAULT_RULES_PATH)
