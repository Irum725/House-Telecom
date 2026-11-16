"""Dashboard summary API router."""

import os
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.exclusion import apply_exclusion_filter, get_active_exclusion_map
from backend.stage import estimate_completion_month
from shared.database import get_db
from shared.enums import BuildingStage, ExclusionStatus
from shared.models import ApiTrafficLog, Building, ExclusionHistory, ReportRun
from shared.schemas import (
    BuildingSummary,
    DashboardSummaryResponse,
    ExclusionStatusCount,
    MonthlyBuildingStat,
    MonthlySummaryResponse,
    ReportRunItem,
    StageCount,
)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _building_to_summary(
    building: Building,
    active_exclusion_status: Optional[ExclusionStatus] = None,
) -> BuildingSummary:
    return BuildingSummary(
        mgm_pmsrgst_pk=building.mgm_pmsrgst_pk,
        bld_rgst_pk=building.bld_rgst_pk,
        sigungu_cd=building.sigungu_cd,
        bjdong_cd=building.bjdong_cd,
        plat_plc=building.plat_plc,
        bld_nm=building.bld_nm,
        main_purps_cd_nm=building.main_purps_cd_nm,
        tot_area=building.tot_area,
        hhld_cnt=building.hhld_cnt,
        dong_cnt=building.dong_cnt,
        arch_pms_day=building.arch_pms_day,
        stcns_sched_day=building.stcns_sched_day,
        real_stcns_day=building.real_stcns_day,
        use_apr_day=building.use_apr_day,
        stage=building.stage,
        priority_score=building.priority_score,
        expected_completion_month=estimate_completion_month(
            real_stcns_day=building.real_stcns_day,
            stcns_sched_day=building.stcns_sched_day,
            use_apr_day=building.use_apr_day,
            tot_area=building.tot_area,
        ),
        is_excluded=active_exclusion_status is not None,
        active_exclusion_status=active_exclusion_status,
    )


@router.get("", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    sigungu_cd: Optional[str] = Query(default=None, min_length=5, max_length=5),
    db: Session = Depends(get_db),
) -> DashboardSummaryResponse:
    """Return KPI counts, stage breakdown, exclusion breakdown, top buildings, and recent reports."""
    base_filter = []
    if sigungu_cd:
        base_filter.append(Building.sigungu_cd == sigungu_cd)

    total_buildings = db.scalar(
        select(func.count(Building.mgm_pmsrgst_pk)).where(*base_filter)
    ) or 0

    active_excl_subq = (
        select(ExclusionHistory.mgm_pmsrgst_pk)
        .where(ExclusionHistory.is_active.is_(True))
        .distinct()
    )

    excluded_count = db.scalar(
        select(func.count(Building.mgm_pmsrgst_pk)).where(
            *base_filter,
            Building.mgm_pmsrgst_pk.in_(active_excl_subq),
        )
    ) or 0

    active_targets = max(0, total_buildings - excluded_count)

    current_yyyymm = datetime.now(timezone.utc).strftime("%Y%m")
    new_starts_this_month = db.scalar(
        select(func.count(Building.mgm_pmsrgst_pk)).where(
            *base_filter,
            ~Building.mgm_pmsrgst_pk.in_(active_excl_subq),
            Building.real_stcns_day.is_not(None),
            Building.real_stcns_day.like(f"{current_yyyymm}%"),
        )
    ) or 0

    stage_rows = db.execute(
        select(Building.stage, func.count(Building.mgm_pmsrgst_pk))
        .where(*base_filter, ~Building.mgm_pmsrgst_pk.in_(active_excl_subq))
        .group_by(Building.stage)
    ).all()
    stage_map = {stage: count for stage, count in stage_rows}
    stage_counts = [
        StageCount(stage=stage, count=stage_map.get(stage, 0))
        for stage in BuildingStage
    ]

    excl_query = (
        select(ExclusionHistory.status, func.count(func.distinct(ExclusionHistory.mgm_pmsrgst_pk)))
        .join(Building, Building.mgm_pmsrgst_pk == ExclusionHistory.mgm_pmsrgst_pk)
        .where(ExclusionHistory.is_active.is_(True), *base_filter)
        .group_by(ExclusionHistory.status)
    )
    excl_rows = db.execute(excl_query).all()
    excl_map = {status: count for status, count in excl_rows}
    exclusion_counts = [
        ExclusionStatusCount(status=status, count=excl_map.get(status, 0))
        for status in ExclusionStatus
    ]

    near_completion_rows = db.scalars(
        select(Building)
        .where(
            *base_filter,
            ~Building.mgm_pmsrgst_pk.in_(active_excl_subq),
            Building.stage == BuildingStage.NEAR_COMPLETION,
        )
        .order_by(Building.priority_score.desc(), Building.updated_at.desc())
        .limit(20)
    ).all()
    near_completion_top20 = [_building_to_summary(b) for b in near_completion_rows]

    top_priority_rows = db.scalars(
        select(Building)
        .where(
            *base_filter,
            ~Building.mgm_pmsrgst_pk.in_(active_excl_subq),
        )
        .order_by(Building.priority_score.desc(), Building.updated_at.desc())
        .limit(20)
    ).all()
    top_priority_buildings = [_building_to_summary(b) for b in top_priority_rows]

    report_query = select(ReportRun).order_by(ReportRun.run_at.desc(), ReportRun.id.desc()).limit(10)
    if sigungu_cd:
        report_query = (
            select(ReportRun)
            .where(ReportRun.region_code.like(f"{sigungu_cd}%"))
            .order_by(ReportRun.run_at.desc(), ReportRun.id.desc())
            .limit(10)
        )
    recent_reports = [ReportRunItem.model_validate(r) for r in db.scalars(report_query).all()]

    default_limit = int(os.getenv("DATA_GO_KR_DAILY_LIMIT", "10000"))
    traffic = db.scalar(select(ApiTrafficLog).where(ApiTrafficLog.log_date == date.today()))
    api_traffic_today = traffic.request_count if traffic else 0
    api_daily_limit = traffic.daily_limit if traffic else default_limit

    return DashboardSummaryResponse(
        total_buildings=total_buildings,
        active_targets=active_targets,
        excluded_count=excluded_count,
        new_starts_this_month=new_starts_this_month,
        stage_counts=stage_counts,
        exclusion_counts=exclusion_counts,
        near_completion_top20=near_completion_top20,
        top_priority_buildings=top_priority_buildings,
        recent_reports=recent_reports,
        api_traffic_today=api_traffic_today,
        api_daily_limit=api_daily_limit,
    )


def _extract_building_month(
    building: Building,
    basis: Literal["use_apr_day", "arch_pms_day", "real_stcns_day", "all"],
) -> Optional[str]:
    if basis == "use_apr_day":
        raw = building.use_apr_day
    elif basis == "arch_pms_day":
        raw = building.arch_pms_day
    elif basis == "real_stcns_day":
        raw = building.real_stcns_day
    else:
        raw = (
            building.use_apr_day
            or building.real_stcns_day
            or building.stcns_sched_day
            or building.arch_pms_day
        )

    if not raw or len(raw) < 6 or not raw[:6].isdigit():
        return None
    year = int(raw[:4])
    mon = int(raw[4:6])
    if year < 1900 or mon < 1 or mon > 12:
        return None
    return f"{year:04d}-{mon:02d}"


@router.get("/monthly", response_model=MonthlySummaryResponse)
def get_monthly_buildings(
    sigungu_cd: Optional[str] = Query(default=None, min_length=5, max_length=5),
    bjdong_cd: Optional[str] = Query(default=None, min_length=5, max_length=5),
    months: int = Query(default=12, ge=1, le=60),
    month: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    basis: Literal["use_apr_day", "arch_pms_day", "real_stcns_day", "all"] = Query(default="all"),
    include_excluded: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> MonthlySummaryResponse:
    """Return monthly new-building statistics and buildings for the selected month."""
    stmt = select(Building)
    stmt = apply_exclusion_filter(stmt, include_excluded=include_excluded)
    if sigungu_cd:
        stmt = stmt.where(Building.sigungu_cd == sigungu_cd)
    if bjdong_cd and bjdong_cd != "00000":
        stmt = stmt.where(Building.bjdong_cd == bjdong_cd)

    rows = list(
        db.scalars(
            stmt.order_by(Building.priority_score.desc(), Building.mgm_pmsrgst_pk.asc())
        ).all()
    )

    grouped: dict[str, list[Building]] = defaultdict(list)
    for b in rows:
        ym = _extract_building_month(b, basis)
        if ym is not None:
            grouped[ym].append(b)

    sorted_months = sorted(grouped.keys(), reverse=True)[:months]

    monthly_stats: list[MonthlyBuildingStat] = []
    for ym in sorted_months:
        b_list = grouped[ym]
        stat = MonthlyBuildingStat(
            month=ym,
            permitted_count=sum(1 for b in b_list if b.stage == BuildingStage.PERMITTED),
            start_scheduled_count=sum(1 for b in b_list if b.stage == BuildingStage.START_SCHEDULED),
            under_construction_count=sum(
                1 for b in b_list if b.stage == BuildingStage.UNDER_CONSTRUCTION
            ),
            near_completion_count=sum(1 for b in b_list if b.stage == BuildingStage.NEAR_COMPLETION),
            use_approved_count=sum(1 for b in b_list if b.stage == BuildingStage.USE_APPROVED),
            total_count=len(b_list),
            total_hhld_cnt=sum(b.hhld_cnt or 0 for b in b_list),
            total_tot_area=round(sum(b.tot_area or 0.0 for b in b_list), 2),
        )
        monthly_stats.append(stat)

    selected_month = month if month is not None else (sorted_months[0] if sorted_months else None)
    selected_buildings = grouped.get(selected_month, []) if selected_month else []

    pks = [b.mgm_pmsrgst_pk for b in selected_buildings]
    excl_map = get_active_exclusion_map(db, pks) if (include_excluded and pks) else {}
    summaries = [
        _building_to_summary(
            b,
            excl_map[b.mgm_pmsrgst_pk].status if b.mgm_pmsrgst_pk in excl_map else None,
        )
        for b in selected_buildings
    ]

    return MonthlySummaryResponse(
        months=monthly_stats,
        selected_month=selected_month,
        buildings=summaries,
        total=len(summaries),
    )
