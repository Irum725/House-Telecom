"""Boundary-value unit tests for backend/stage classification and priority scoring."""

from datetime import date, datetime
from pathlib import Path

import pytest

from backend.stage import (
    DEFAULT_RULES_PATH,
    ScoringWeights,
    StageRules,
    calculate_priority_score,
    classify_stage,
    estimate_completion_month,
    evaluate_building,
    load_rules,
    months_elapsed,
    parse_yyyymmdd,
    resolve_estimated_duration_months,
    resolve_near_completion_months,
    score_households,
    score_main_purpose,
    score_stage,
    score_total_area,
)
from shared.enums import BuildingStage
from shared.models import Building


class TestDateParsingAndElapsed:
    """Boundary tests for parse_yyyymmdd and months_elapsed."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("20250315", date(2025, 3, 15)),
            (" 20250315 ", date(2025, 3, 15)),
            ("2025-03-15", date(2025, 3, 15)),
            (date(2025, 3, 15), date(2025, 3, 15)),
            (datetime(2025, 3, 15, 9, 30), date(2025, 3, 15)),
            (None, None),
            ("", None),
            ("   ", None),
            ("00000000", None),
            ("20250230", None),  # invalid calendar day
            ("20251301", None),  # invalid month
            ("invalid", None),
        ],
    )
    def test_parse_yyyymmdd_boundaries(self, raw, expected):
        assert parse_yyyymmdd(raw) == expected

    def test_months_elapsed_exact_and_minus_one_day(self):
        start = date(2025, 1, 15)
        assert months_elapsed(start, date(2026, 1, 15)) == 12
        assert months_elapsed(start, date(2026, 1, 14)) == 11
        assert months_elapsed(start, date(2025, 1, 15)) == 0
        assert months_elapsed(start, date(2024, 12, 31)) == 0  # future start


class TestStageClassification:
    """Boundary-value tests for BuildingStage classification."""

    def test_use_approved_takes_precedence_over_all(self):
        stage = classify_stage(
            use_apr_day="20260101",
            real_stcns_day="20250101",
            stcns_sched_day="20241201",
            arch_pms_day="20241001",
            reference_date=date(2026, 2, 1),
        )
        assert stage == BuildingStage.USE_APPROVED

    def test_use_approved_even_when_real_stcns_missing(self):
        assert classify_stage(use_apr_day="20260101") == BuildingStage.USE_APPROVED

    def test_near_completion_exact_12_months_when_area_missing(self):
        stage = classify_stage(
            real_stcns_day="20250115",
            tot_area=None,
            reference_date=date(2026, 1, 15),
        )
        assert stage == BuildingStage.NEAR_COMPLETION

    def test_under_construction_one_day_before_12_months(self):
        stage = classify_stage(
            real_stcns_day="20250115",
            tot_area=None,
            reference_date=date(2026, 1, 14),
        )
        assert stage == BuildingStage.UNDER_CONSTRUCTION

    def test_under_construction_when_real_stcns_is_in_future(self):
        stage = classify_stage(
            real_stcns_day="20260601",
            reference_date=date(2026, 1, 15),
        )
        assert stage == BuildingStage.UNDER_CONSTRUCTION

    @pytest.mark.parametrize(
        ("tot_area", "expected_months"),
        [
            (0.0, 6),
            (999.99, 6),
            (1000.0, 10),
            (4999.99, 10),
            (5000.0, 12),
            (19999.99, 12),
            (20000.0, 18),
            (100000.0, 18),
            (None, 12),
        ],
    )
    def test_area_threshold_boundaries(self, tot_area, expected_months):
        assert resolve_near_completion_months(tot_area) == expected_months

    def test_small_building_near_completion_at_6_months(self):
        # tot_area < 1000 => 6 months
        assert (
            classify_stage(
                real_stcns_day="20250701",
                tot_area=999.0,
                reference_date=date(2026, 1, 1),
            )
            == BuildingStage.NEAR_COMPLETION
        )
        assert (
            classify_stage(
                real_stcns_day="20250701",
                tot_area=999.0,
                reference_date=date(2025, 12, 31),
            )
            == BuildingStage.UNDER_CONSTRUCTION
        )

    def test_large_building_requires_18_months(self):
        # tot_area >= 20000 => 18 months
        assert (
            classify_stage(
                real_stcns_day="20240701",
                tot_area=20000.0,
                reference_date=date(2025, 12, 31),
            )
            == BuildingStage.UNDER_CONSTRUCTION
        )
        assert (
            classify_stage(
                real_stcns_day="20240701",
                tot_area=20000.0,
                reference_date=date(2026, 1, 1),
            )
            == BuildingStage.NEAR_COMPLETION
        )

    def test_start_scheduled_when_no_real_or_use_apr(self):
        stage = classify_stage(
            use_apr_day="  ",
            real_stcns_day="00000000",
            stcns_sched_day="20260501",
            arch_pms_day="20260110",
        )
        assert stage == BuildingStage.START_SCHEDULED

    def test_permitted_when_only_arch_pms_day_present(self):
        assert classify_stage(arch_pms_day="20260110") == BuildingStage.PERMITTED

    def test_permitted_default_when_all_dates_missing(self):
        assert classify_stage() == BuildingStage.PERMITTED

    def test_override_near_completion_months(self):
        stage = classify_stage(
            real_stcns_day="20251001",
            tot_area=50000.0,
            reference_date=date(2026, 1, 1),
            near_completion_months=3,
        )
        assert stage == BuildingStage.NEAR_COMPLETION

    def test_load_custom_rules_yaml(self, tmp_path: Path):
        custom_yaml = tmp_path / "custom_rules.yaml"
        custom_yaml.write_text(
            "stage_classification:\n"
            "  default_near_completion_months: 4\n"
            "  use_area_adjustment: false\n",
            encoding="utf-8",
        )
        rules = load_rules(custom_yaml)
        assert isinstance(rules, StageRules)
        assert (
            classify_stage(
                real_stcns_day="20250901",
                tot_area=50000.0,
                reference_date=date(2026, 1, 1),
                rules=rules,
            )
            == BuildingStage.NEAR_COMPLETION
        )


class TestPriorityScoring:
    """Boundary-value tests for telecom priority scoring."""

    def test_default_rules_yaml_loads(self):
        rules = load_rules(DEFAULT_RULES_PATH)
        assert rules.priority_scoring.weights.total == pytest.approx(1.0)

    def test_max_score_is_100(self):
        score = calculate_priority_score(
            hhld_cnt=500,
            tot_area=50000.0,
            main_purps_cd_nm="공동주택",
            stage=BuildingStage.NEAR_COMPLETION,
        )
        assert score == 100.0

    def test_values_above_max_clamp_to_100(self):
        score = calculate_priority_score(
            hhld_cnt=2000,
            tot_area=200000.0,
            main_purps_cd_nm="공동주택",
            stage=BuildingStage.NEAR_COMPLETION,
        )
        assert score == 100.0

    def test_zero_and_none_inputs_stay_within_bounds(self):
        score = calculate_priority_score(
            hhld_cnt=None,
            tot_area=None,
            main_purps_cd_nm=None,
            stage=BuildingStage.USE_APPROVED,
        )
        assert 0.0 <= score <= 100.0
        # 0.35*0 + 0.25*0 + 0.20*20 + 0.20*15 = 7.0
        assert score == 7.0

    def test_households_subscore_boundaries(self):
        assert score_households(None) == 0.0
        assert score_households(0) == 0.0
        assert score_households(-5) == 0.0
        assert score_households(1) == 15.0
        assert score_households(500) == 100.0
        assert score_households(999) == 100.0

    def test_tot_area_subscore_boundaries(self):
        assert score_total_area(None) == 0.0
        assert score_total_area(0.0) == 0.0
        assert score_total_area(300.0) == 20.0
        assert score_total_area(50000.0) == 100.0
        assert score_total_area(75000.0) == 100.0

    def test_purpose_exact_substring_and_fallback(self):
        assert score_main_purpose("공동주택") == 100.0
        assert score_main_purpose("제2종근린생활시설(일반음식점)") == 65.0
        assert score_main_purpose("미분류특수시설") == 40.0
        assert score_main_purpose("") == 20.0
        assert score_main_purpose(None) == 20.0

    def test_stage_urgency_ordering(self):
        ordered = [
            score_stage(BuildingStage.NEAR_COMPLETION),
            score_stage(BuildingStage.UNDER_CONSTRUCTION),
            score_stage(BuildingStage.START_SCHEDULED),
            score_stage(BuildingStage.PERMITTED),
            score_stage(BuildingStage.USE_APPROVED),
        ]
        assert ordered == sorted(ordered, reverse=True)
        assert len(set(ordered)) == len(ordered)

    def test_custom_weights_override(self):
        weights = ScoringWeights(hhld_cnt=1.0, tot_area=0.0, main_purps=0.0, stage=0.0)
        assert (
            calculate_priority_score(
                hhld_cnt=500,
                tot_area=0.0,
                main_purps_cd_nm=None,
                stage=BuildingStage.USE_APPROVED,
                weights=weights,
            )
            == 100.0
        )

    def test_zero_total_weights_returns_zero(self):
        weights = ScoringWeights(hhld_cnt=0.0, tot_area=0.0, main_purps=0.0, stage=0.0)
        assert (
            calculate_priority_score(
                hhld_cnt=500,
                tot_area=50000.0,
                main_purps_cd_nm="공동주택",
                stage=BuildingStage.NEAR_COMPLETION,
                weights=weights,
            )
            == 0.0
        )

    def test_evaluate_building_dict_and_orm(self):
        payload = {
            "use_apr_day": None,
            "real_stcns_day": "20250101",
            "stcns_sched_day": "20241101",
            "arch_pms_day": "20240901",
            "tot_area": 12000.0,
            "hhld_cnt": 120,
            "main_purps_cd_nm": "공동주택",
        }
        stage_d, score_d = evaluate_building(payload, reference_date=date(2026, 1, 1))

        orm_obj = Building(
            mgm_pmsrgst_pk="PK-001",
            sigungu_cd="41135",
            bjdong_cd="10300",
            **payload,
        )
        stage_o, score_o = evaluate_building(orm_obj, reference_date=date(2026, 1, 1))

        assert stage_d == BuildingStage.NEAR_COMPLETION
        assert stage_o == stage_d
        assert score_o == score_d
        assert 70.0 < score_d <= 100.0


class TestEstimatedCompletionMonth:
    """Boundary-value tests for estimate_completion_month."""

    @pytest.mark.parametrize(
        ("tot_area", "expected_months"),
        [
            (0.0, 8),
            (999.99, 8),
            (1000.0, 12),
            (4999.99, 12),
            (5000.0, 16),
            (19999.99, 16),
            (20000.0, 24),
            (None, 14),
        ],
    )
    def test_estimated_duration_area_boundaries(self, tot_area, expected_months):
        assert resolve_estimated_duration_months(tot_area) == expected_months

    def test_returns_none_when_use_apr_day_is_set(self):
        assert (
            estimate_completion_month(
                real_stcns_day="20250115",
                stcns_sched_day="20241201",
                use_apr_day="20260110",
                tot_area=3000.0,
            )
            is None
        )

    def test_prefers_real_stcns_day_over_stcns_sched_day(self):
        # 2025-03 + 12 months (tot_area=1500) -> 2026-03
        assert (
            estimate_completion_month(
                real_stcns_day="20250315",
                stcns_sched_day="20250101",
                use_apr_day=None,
                tot_area=1500.0,
            )
            == "2026-03"
        )

    def test_falls_back_to_stcns_sched_day_and_wraps_year(self):
        # 2025-11 + 8 months (tot_area=500) -> 2026-07
        assert (
            estimate_completion_month(
                real_stcns_day=None,
                stcns_sched_day="20251120",
                use_apr_day="",
                tot_area=500.0,
            )
            == "2026-07"
        )

    def test_default_duration_when_tot_area_missing(self):
        # 2025-01 + 14 months -> 2026-03
        assert (
            estimate_completion_month(
                real_stcns_day="20250101",
                stcns_sched_day=None,
                use_apr_day=None,
                tot_area=None,
            )
            == "2026-03"
        )

    def test_returns_none_when_no_valid_start_date(self):
        assert (
            estimate_completion_month(
                real_stcns_day="00000000",
                stcns_sched_day=" ",
                use_apr_day=None,
                tot_area=2000.0,
            )
            is None
        )

    def test_custom_rules_estimated_duration(self, tmp_path: Path):
        custom_yaml = tmp_path / "custom_duration.yaml"
        custom_yaml.write_text(
            "stage_classification:\n"
            "  estimated_duration_months:\n"
            "    default_months: 10\n"
            "    area_thresholds:\n"
            "      - max_tot_area: null\n"
            "        months: 10\n",
            encoding="utf-8",
        )
        rules = load_rules(custom_yaml)
        assert (
            estimate_completion_month(
                real_stcns_day="20250601",
                stcns_sched_day=None,
                use_apr_day=None,
                tot_area=50000.0,
                rules=rules,
            )
            == "2026-04"
        )
