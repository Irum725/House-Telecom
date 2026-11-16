"""Pydantic v2 request/response schemas for House-Telecom REST API."""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from shared.enums import BuildingStage, ExclusionStatus


# ---------------------------------------------------------------------------
# Regions
# ---------------------------------------------------------------------------
class RegionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    sido_cd: str
    sigungu_cd: str
    bjdong_cd: str
    sido_name: str
    sigungu_name: Optional[str] = None
    emd_name: Optional[str] = None
    is_active: bool = True


class RegionListResponse(BaseModel):
    items: list[RegionItem]
    total: int


class RegionApiParams(BaseModel):
    sigunguCd: str = Field(..., min_length=5, max_length=5, description="시군구코드 5자리")
    bjdongCd: str = Field(
        default="00000", min_length=5, max_length=5, description="법정동코드 5자리 (전체 시군구는 00000)"
    )


# ---------------------------------------------------------------------------
# Exclusions
# ---------------------------------------------------------------------------
class ExclusionCreateRequest(BaseModel):
    mgm_pmsrgst_pk: str = Field(..., min_length=1, max_length=64)
    actor: str = Field(..., min_length=1, max_length=100)
    status: ExclusionStatus
    reason: Optional[str] = None
    evidence: Optional[str] = Field(default=None, max_length=500)


class ExclusionRestoreRequest(BaseModel):
    restored_by: str = Field(..., min_length=1, max_length=100)


class ExclusionHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mgm_pmsrgst_pk: str
    actor: str
    created_at: datetime
    status: ExclusionStatus
    reason: Optional[str] = None
    evidence: Optional[str] = None
    is_active: bool
    restored_at: Optional[datetime] = None
    restored_by: Optional[str] = None


class ExclusionListResponse(BaseModel):
    items: list[ExclusionHistoryItem]
    total: int


class ExclusionBulkRowResult(BaseModel):
    row_number: int
    identifier: str
    matched_pk: Optional[str] = None
    status: Literal["excluded", "not_found", "error"]
    detail: Optional[str] = None


class ExclusionBulkResponse(BaseModel):
    total_rows: int
    excluded_count: int
    not_found_count: int
    error_count: int
    results: list[ExclusionBulkRowResult]


# ---------------------------------------------------------------------------
# Buildings
# ---------------------------------------------------------------------------
class BuildingSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mgm_pmsrgst_pk: str
    bld_rgst_pk: Optional[str] = None
    sigungu_cd: str
    bjdong_cd: str
    plat_plc: Optional[str] = None
    bld_nm: Optional[str] = None
    main_purps_cd_nm: Optional[str] = None
    tot_area: Optional[float] = None
    hhld_cnt: Optional[int] = None
    dong_cnt: Optional[int] = None
    arch_pms_day: Optional[str] = None
    stcns_sched_day: Optional[str] = None
    real_stcns_day: Optional[str] = None
    use_apr_day: Optional[str] = None
    expected_completion_month: Optional[str] = Field(
        default=None,
        description="예상 준공월 (YYYY-MM, 사용승인일 미확정 시 실제착공일/착공예정일 + 연면적 기반 산정)",
    )
    stage: BuildingStage
    priority_score: float
    is_excluded: bool = False
    active_exclusion_status: Optional[ExclusionStatus] = None


class BuildingDetail(BuildingSummary):
    raw_json: Optional[dict[str, Any]] = None
    first_seen_at: datetime
    updated_at: datetime
    exclusion_history: list[ExclusionHistoryItem] = Field(default_factory=list)


class BuildingSearchParams(BaseModel):
    sigungu_cd: Optional[str] = Field(default=None, min_length=5, max_length=5)
    bjdong_cd: Optional[str] = Field(default=None, min_length=5, max_length=5)
    stages: Optional[list[BuildingStage]] = None
    main_purps: Optional[str] = None
    scale: Optional[Literal["all", "small", "large"]] = Field(
        default=None,
        description="규모 필터 (all | small: 단독/다가구/다세대/연립/근린생활시설 또는 연면적 < 1000㎡ | large: 공동주택/아파트/업무시설/오피스텔 또는 연면적 >= 3000㎡)",
    )
    min_hhld_cnt: Optional[int] = Field(default=None, ge=0)
    min_tot_area: Optional[float] = Field(default=None, ge=0.0)
    min_priority_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    date_from: Optional[str] = Field(default=None, min_length=8, max_length=8, description="허가/착공 시작일 YYYYMMDD")
    date_to: Optional[str] = Field(default=None, min_length=8, max_length=8, description="허가/착공 종료일 YYYYMMDD")
    q: Optional[str] = Field(default=None, description="건물명 또는 대지위치 검색어")
    include_excluded: bool = False
    sort_by: Literal[
        "priority_score",
        "tot_area",
        "hhld_cnt",
        "arch_pms_day",
        "use_apr_day",
        "updated_at",
    ] = "priority_score"
    sort_order: Literal["asc", "desc"] = "desc"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)


class PaginatedBuildingsResponse(BaseModel):
    items: list[BuildingSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class BuildingSyncRequest(BaseModel):
    sigungu_cd: str = Field(..., min_length=5, max_length=5)
    bjdong_cd: str = Field(default="00000", min_length=5, max_length=5)
    num_of_rows: int = Field(default=100, ge=1, le=1000)
    max_pages: Optional[int] = Field(default=None, ge=1)
    use_fixture: bool = Field(default=False, description="True면 외부 API 대신 로컬 fixture 데이터로 수집")


class BuildingSyncResponse(BaseModel):
    sigungu_cd: str
    bjdong_cd: str
    fetched_count: int
    created_count: int
    updated_count: int
    api_calls_used: int
    remaining_daily_quota: int


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
class ReportGenerateRequest(BaseModel):
    sigungu_cd: str = Field(..., min_length=5, max_length=5)
    bjdong_cd: str = Field(default="00000", min_length=5, max_length=5)
    stages: Optional[list[BuildingStage]] = None
    include_excluded: bool = False
    formats: list[Literal["excel", "pdf"]] = Field(default_factory=lambda: ["excel", "pdf"])


class ReportRunItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    region_code: str
    run_at: datetime
    excel_path: Optional[str] = None
    pdf_path: Optional[str] = None
    total_count: int
    new_count: int
    stage_changed_count: int
    diff_json: Optional[dict[str, Any]] = None


class ReportListResponse(BaseModel):
    items: list[ReportRunItem]
    total: int


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
class StageCount(BaseModel):
    stage: BuildingStage
    count: int


class ExclusionStatusCount(BaseModel):
    status: ExclusionStatus
    count: int


class DashboardSummaryResponse(BaseModel):
    total_buildings: int
    active_targets: int
    excluded_count: int
    new_starts_this_month: int = 0
    stage_counts: list[StageCount]
    exclusion_counts: list[ExclusionStatusCount]
    near_completion_top20: list[BuildingSummary] = Field(default_factory=list)
    top_priority_buildings: list[BuildingSummary]
    recent_reports: list[ReportRunItem]
    api_traffic_today: int
    api_daily_limit: int


class MonthlyBuildingStat(BaseModel):
    month: str = Field(..., description="월 (YYYY-MM)")
    permitted_count: int = 0
    start_scheduled_count: int = 0
    under_construction_count: int = 0
    near_completion_count: int = 0
    use_approved_count: int = 0
    total_count: int = 0
    total_hhld_cnt: int = 0
    total_tot_area: float = 0.0


class MonthlySummaryResponse(BaseModel):
    months: list[MonthlyBuildingStat]
    selected_month: Optional[str] = None
    buildings: list[BuildingSummary] = Field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Jobs / Scheduler
# ---------------------------------------------------------------------------
class InterestRegionCreate(BaseModel):
    sigungu_cd: str = Field(..., min_length=5, max_length=5)
    bjdong_cd: str = Field(default="00000", min_length=5, max_length=5)
    name: str = Field(..., min_length=1, max_length=100)
    is_active: bool = True
    cron_expr: str = Field(default="0 6 * * 1", min_length=5, max_length=64)


class InterestRegionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sigungu_cd: str
    bjdong_cd: str
    name: str
    is_active: bool
    cron_expr: str
    created_at: datetime


class InterestRegionListResponse(BaseModel):
    items: list[InterestRegionItem]
    total: int


class JobTriggerRequest(BaseModel):
    interest_region_id: Optional[int] = None
    sigungu_cd: Optional[str] = Field(default=None, min_length=5, max_length=5)
    bjdong_cd: str = Field(default="00000", min_length=5, max_length=5)


class JobTriggerResponse(BaseModel):
    status: str
    triggered_regions: list[str]
    report_run_ids: list[int]
    message: str
