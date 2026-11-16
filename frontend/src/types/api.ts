export type BuildingStage =
  | 'PERMITTED'
  | 'START_SCHEDULED'
  | 'UNDER_CONSTRUCTION'
  | 'NEAR_COMPLETION'
  | 'USE_APPROVED'

export const BUILDING_STAGE_LABELS: Record<BuildingStage, string> = {
  PERMITTED: '건축허가',
  START_SCHEDULED: '착공예정',
  UNDER_CONSTRUCTION: '착공진행',
  NEAR_COMPLETION: '준공임박',
  USE_APPROVED: '사용승인',
}

export const BUILDING_STAGE_ORDER: BuildingStage[] = [
  'PERMITTED',
  'START_SCHEDULED',
  'UNDER_CONSTRUCTION',
  'NEAR_COMPLETION',
  'USE_APPROVED',
]

export type ExclusionStatus =
  | 'TELECOM_DONE_FIELD'
  | 'TELECOM_DONE_SYSTEM'
  | 'NOT_TARGET'
  | 'ON_HOLD'

export const EXCLUSION_STATUS_LABELS: Record<ExclusionStatus, string> = {
  TELECOM_DONE_FIELD: '통신공사 완료(실사)',
  TELECOM_DONE_SYSTEM: '통신공사 완료(시스템)',
  NOT_TARGET: '대상아님',
  ON_HOLD: '보류',
}

export const EXCLUSION_ACTIONS: { status: ExclusionStatus; label: string; shortLabel: string }[] = [
  { status: 'TELECOM_DONE_FIELD', label: '통신공사 완료(실사)', shortLabel: '완료(실사)' },
  { status: 'TELECOM_DONE_SYSTEM', label: '통신공사 완료(시스템)', shortLabel: '완료(시스템)' },
  { status: 'NOT_TARGET', label: '대상아님', shortLabel: '대상아님' },
  { status: 'ON_HOLD', label: '보류', shortLabel: '보류' },
]

export interface RegionItem {
  code: string
  sido_cd: string
  sigungu_cd: string
  bjdong_cd: string
  sido_name: string
  sigungu_name: string | null
  emd_name: string | null
  is_active: boolean
}

export interface RegionListResponse {
  items: RegionItem[]
  total: number
}

export interface BuildingSummary {
  mgm_pmsrgst_pk: string
  bld_rgst_pk: string | null
  sigungu_cd: string
  bjdong_cd: string
  plat_plc: string | null
  bld_nm: string | null
  main_purps_cd_nm: string | null
  tot_area: number | null
  hhld_cnt: number | null
  dong_cnt: number | null
  arch_pms_day: string | null
  stcns_sched_day: string | null
  real_stcns_day: string | null
  use_apr_day: string | null
  stage: BuildingStage
  priority_score: number
  is_excluded: boolean
  active_exclusion_status: ExclusionStatus | null
  expected_completion_month?: string | null
}

export interface ExclusionHistoryItem {
  id: number
  mgm_pmsrgst_pk: string
  actor: string
  created_at: string
  status: ExclusionStatus
  reason: string | null
  evidence: string | null
  is_active: boolean
  restored_at: string | null
  restored_by: string | null
}

export interface BuildingDetail extends BuildingSummary {
  raw_json: Record<string, unknown> | null
  first_seen_at: string
  updated_at: string
  exclusion_history: ExclusionHistoryItem[]
}

export type BuildingSortBy =
  | 'priority_score'
  | 'tot_area'
  | 'hhld_cnt'
  | 'arch_pms_day'
  | 'use_apr_day'
  | 'updated_at'

export type SortOrder = 'asc' | 'desc'

export type BuildingScale = 'all' | 'small' | 'large'

export const BUILDING_SCALE_LABELS: Record<BuildingScale, string> = {
  all: '전체 규모',
  small: '소규모 (단독·다세대·근생)',
  large: '대규모 (공동주택·업무)',
}

export interface BuildingSearchParams {
  sido_cd?: string
  sigungu_cd?: string
  bjdong_cd?: string
  stages?: BuildingStage[]
  scale?: BuildingScale
  main_purps?: string
  min_hhld_cnt?: number
  min_tot_area?: number
  min_priority_score?: number
  date_from?: string
  date_to?: string
  q?: string
  include_excluded?: boolean
  sort_by?: BuildingSortBy
  sort_order?: SortOrder
  page?: number
  page_size?: number
}

export interface PaginatedBuildingsResponse {
  items: BuildingSummary[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface BuildingSyncRequest {
  sigungu_cd: string
  bjdong_cd?: string
  num_of_rows?: number
  max_pages?: number | null
  use_fixture?: boolean
}

export interface BuildingSyncResponse {
  sigungu_cd: string
  bjdong_cd: string
  fetched_count: number
  created_count: number
  updated_count: number
  api_calls_used: number
  remaining_daily_quota: number
}

export interface ExclusionCreateRequest {
  mgm_pmsrgst_pk: string
  actor: string
  status: ExclusionStatus
  reason?: string | null
  evidence?: string | null
}

export interface ExclusionListResponse {
  items: ExclusionHistoryItem[]
  total: number
}

export interface ExclusionBulkRowResult {
  row_number: number
  identifier: string
  matched_pk: string | null
  status: 'excluded' | 'not_found' | 'error'
  detail: string | null
}

export interface ExclusionBulkResponse {
  total_rows: number
  excluded_count: number
  not_found_count: number
  error_count: number
  results: ExclusionBulkRowResult[]
}

export interface ReportGenerateRequest {
  sigungu_cd: string
  bjdong_cd?: string
  stages?: BuildingStage[]
  include_excluded?: boolean
  formats?: ('excel' | 'pdf')[]
}

export interface ReportRunItem {
  id: number
  region_code: string
  run_at: string
  excel_path: string | null
  pdf_path: string | null
  total_count: number
  new_count: number
  stage_changed_count: number
  diff_json: Record<string, unknown> | null
}

export interface StageCount {
  stage: BuildingStage
  count: number
}

export interface ExclusionStatusCount {
  status: ExclusionStatus
  count: number
}

export interface DashboardSummaryResponse {
  total_buildings: number
  active_targets: number
  excluded_count: number
  new_starts_this_month: number
  stage_counts: StageCount[]
  exclusion_counts: ExclusionStatusCount[]
  near_completion_top20: BuildingSummary[]
  top_priority_buildings: BuildingSummary[]
  recent_reports: ReportRunItem[]
  api_traffic_today: number
  api_daily_limit: number
}

export type MonthlyDateBasis = 'use_apr_day' | 'arch_pms_day' | 'real_stcns_day' | 'all'

export const MONTHLY_BASIS_LABELS: Record<MonthlyDateBasis, string> = {
  all: '전체 기준일',
  use_apr_day: '사용승인일 기준',
  real_stcns_day: '실착공일 기준',
  arch_pms_day: '건축허가일 기준',
}

export interface MonthlyBuildingStat {
  month: string
  permitted_count: number
  start_scheduled_count: number
  under_construction_count: number
  near_completion_count: number
  use_approved_count: number
  total_count: number
  total_hhld_cnt: number
  total_tot_area: number
}

export interface MonthlySummaryResponse {
  months: MonthlyBuildingStat[]
  selected_month: string | null
  buildings: BuildingSummary[]
  total: number
}

export interface MonthlyQueryParams {
  sigungu_cd?: string
  bjdong_cd?: string
  months?: number
  month?: string
  basis?: MonthlyDateBasis
  include_excluded?: boolean
}
