"""Buildings search, detail, and collector sync API router."""

import math
import os
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session

from backend.collector import (
    ApiResponseError,
    CollectorError,
    DailyQuotaExceededError,
    sync_buildings,
)
from backend.exclusion import (
    apply_exclusion_filter,
    get_active_exclusion_map,
    get_building_exclusion_history,
)
from backend.stage import estimate_completion_month, evaluate_building
from shared.database import get_db
from shared.enums import BuildingStage
from shared.models import Building
from shared.schemas import (
    BuildingDetail,
    BuildingSummary,
    BuildingSyncRequest,
    BuildingSyncResponse,
    ExclusionHistoryItem,
    PaginatedBuildingsResponse,
)

router = APIRouter(prefix="/api/buildings", tags=["buildings"])

SORT_COLUMNS = {
    "priority_score": Building.priority_score,
    "tot_area": Building.tot_area,
    "hhld_cnt": Building.hhld_cnt,
    "arch_pms_day": Building.arch_pms_day,
    "use_apr_day": Building.use_apr_day,
    "updated_at": Building.updated_at,
}


def _to_building_summary(
    building: Building,
    active_excl_map: dict,
) -> BuildingSummary:
    excl = active_excl_map.get(building.mgm_pmsrgst_pk)
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
        is_excluded=excl is not None,
        active_exclusion_status=excl.status if excl is not None else None,
    )


@router.get("", response_model=PaginatedBuildingsResponse)
def list_buildings(
    sigungu_cd: Optional[str] = Query(default=None, min_length=5, max_length=5),
    bjdong_cd: Optional[str] = Query(default=None, min_length=5, max_length=5),
    stages: Optional[list[BuildingStage]] = Query(default=None),
    main_purps: Optional[str] = Query(default=None),
    scale: Optional[Literal["all", "small", "large"]] = Query(default=None),
    min_hhld_cnt: Optional[int] = Query(default=None, ge=0),
    min_tot_area: Optional[float] = Query(default=None, ge=0.0),
    min_priority_score: Optional[float] = Query(default=None, ge=0.0, le=100.0),
    date_from: Optional[str] = Query(default=None, min_length=8, max_length=8),
    date_to: Optional[str] = Query(default=None, min_length=8, max_length=8),
    q: Optional[str] = Query(default=None),
    include_excluded: bool = Query(default=False),
    sort_by: Literal[
        "priority_score",
        "tot_area",
        "hhld_cnt",
        "arch_pms_day",
        "use_apr_day",
        "updated_at",
    ] = Query(default="priority_score"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> PaginatedBuildingsResponse:
    """Search, filter, sort, and paginate buildings."""
    stmt = select(Building)
    stmt = apply_exclusion_filter(stmt, include_excluded=include_excluded)

    if sigungu_cd:
        stmt = stmt.where(Building.sigungu_cd == sigungu_cd)
    if bjdong_cd and bjdong_cd != "00000":
        stmt = stmt.where(Building.bjdong_cd == bjdong_cd)
    if stages:
        stmt = stmt.where(Building.stage.in_(stages))
    if main_purps:
        stmt = stmt.where(Building.main_purps_cd_nm.ilike(f"%{main_purps.strip()}%"))
    if scale == "small":
        stmt = stmt.where(
            or_(
                Building.main_purps_cd_nm.ilike("%단독%"),
                Building.main_purps_cd_nm.ilike("%다가구%"),
                Building.main_purps_cd_nm.ilike("%다세대%"),
                Building.main_purps_cd_nm.ilike("%연립%"),
                Building.main_purps_cd_nm.ilike("%근린생활시설%"),
                Building.tot_area < 1000.0,
            )
        )
    elif scale == "large":
        stmt = stmt.where(
            or_(
                Building.main_purps_cd_nm.ilike("%공동주택%"),
                Building.main_purps_cd_nm.ilike("%아파트%"),
                Building.main_purps_cd_nm.ilike("%주상복합%"),
                Building.main_purps_cd_nm.ilike("%업무시설%"),
                Building.main_purps_cd_nm.ilike("%오피스텔%"),
                Building.tot_area >= 3000.0,
            )
        )
    if min_hhld_cnt is not None:
        stmt = stmt.where(Building.hhld_cnt >= min_hhld_cnt)
    if min_tot_area is not None:
        stmt = stmt.where(Building.tot_area >= min_tot_area)
    if min_priority_score is not None:
        stmt = stmt.where(Building.priority_score >= min_priority_score)

    effective_date = func.coalesce(
        Building.real_stcns_day,
        Building.stcns_sched_day,
        Building.arch_pms_day,
    )
    if date_from:
        stmt = stmt.where(effective_date >= date_from)
    if date_to:
        stmt = stmt.where(effective_date <= date_to)

    if q and q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Building.bld_nm.ilike(term),
                Building.plat_plc.ilike(term),
                Building.mgm_pmsrgst_pk.ilike(term),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 0

    sort_col = SORT_COLUMNS[sort_by]
    order_clause = desc(sort_col) if sort_order == "desc" else asc(sort_col)
    offset = (page - 1) * page_size

    rows = list(
        db.scalars(
            stmt.order_by(order_clause, Building.mgm_pmsrgst_pk.asc())
            .offset(offset)
            .limit(page_size)
        ).all()
    )

    pks = [b.mgm_pmsrgst_pk for b in rows]
    active_excl_map = get_active_exclusion_map(db, pks) if pks else {}
    items = [_to_building_summary(b, active_excl_map) for b in rows]

    return PaginatedBuildingsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/sync", response_model=BuildingSyncResponse)
def sync_region_buildings(
    payload: BuildingSyncRequest,
    db: Session = Depends(get_db),
) -> BuildingSyncResponse:
    """Collect building permit data for a region and re-evaluate stage & priority score."""
    service_key = os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip()
    has_real_key = bool(service_key) and service_key != "your_data_go_kr_service_key_here"
    effective_use_fixture = payload.use_fixture or not has_real_key

    effective_req = payload.model_copy(update={"use_fixture": effective_use_fixture})

    try:
        result = sync_buildings(db, effective_req, service_key=service_key if has_real_key else None)
    except DailyQuotaExceededError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except ApiResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except CollectorError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    stmt = select(Building).where(Building.sigungu_cd == payload.sigungu_cd)
    if payload.bjdong_cd != "00000":
        stmt = stmt.where(Building.bjdong_cd == payload.bjdong_cd)

    buildings = db.scalars(stmt).all()
    for building in buildings:
        stage, score = evaluate_building(building)
        building.stage = stage
        building.priority_score = score
    db.commit()

    return result


@router.get("/{mgm_pmsrgst_pk}", response_model=BuildingDetail)
def get_building_detail(
    mgm_pmsrgst_pk: str,
    db: Session = Depends(get_db),
) -> BuildingDetail:
    """Return full building details including raw_json and exclusion history."""
    building = db.get(Building, mgm_pmsrgst_pk)
    if building is None:
        raise HTTPException(status_code=404, detail=f"Building not found: {mgm_pmsrgst_pk}")

    history_rows = get_building_exclusion_history(db, mgm_pmsrgst_pk)
    active_excl = next((h for h in history_rows if h.is_active), None)

    return BuildingDetail(
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
        is_excluded=active_excl is not None,
        active_exclusion_status=active_excl.status if active_excl is not None else None,
        raw_json=building.raw_json,
        first_seen_at=building.first_seen_at,
        updated_at=building.updated_at,
        exclusion_history=[ExclusionHistoryItem.model_validate(h) for h in history_rows],
    )
