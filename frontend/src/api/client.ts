import type {
  BuildingDetail,
  BuildingSearchParams,
  BuildingSyncRequest,
  BuildingSyncResponse,
  DashboardSummaryResponse,
  ExclusionBulkResponse,
  ExclusionCreateRequest,
  ExclusionHistoryItem,
  ExclusionListResponse,
  ExclusionStatus,
  MonthlyQueryParams,
  MonthlySummaryResponse,
  PaginatedBuildingsResponse,
  RegionListResponse,
  ReportGenerateRequest,
  ReportRunItem,
} from '../types/api'

const API_BASE = '/api'

export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) {
    let detail = `요청 실패 (${response.status})`
    try {
      const data = await response.json()
      if (typeof data?.detail === 'string') {
        detail = data.detail
      } else if (data?.detail) {
        detail = JSON.stringify(data.detail)
      }
    } catch {
      // ignore non-JSON error body
    }
    throw new ApiError(response.status, detail)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export async function fetchHealth(): Promise<{ status?: string; live_api_configured?: boolean }> {
  return requestJson<{ status?: string; live_api_configured?: boolean }>(`${API_BASE}/config`)
}

export async function fetchSido(): Promise<RegionListResponse> {
  return requestJson<RegionListResponse>(`${API_BASE}/regions/sido`)
}

export async function fetchSigungu(sidoCd: string): Promise<RegionListResponse> {
  const qs = new URLSearchParams({ sido_cd: sidoCd })
  return requestJson<RegionListResponse>(`${API_BASE}/regions/sigungu?${qs.toString()}`)
}

export async function fetchEmd(sigunguCd: string): Promise<RegionListResponse> {
  const qs = new URLSearchParams({ sigungu_cd: sigunguCd })
  return requestJson<RegionListResponse>(`${API_BASE}/regions/emd?${qs.toString()}`)
}

export async function fetchDashboard(params?: {
  sido_cd?: string
  sigungu_cd?: string
  bjdong_cd?: string
}): Promise<DashboardSummaryResponse> {
  const qs = new URLSearchParams()
  if (params?.sigungu_cd) {
    qs.set('sigungu_cd', params.sigungu_cd)
  } else if (params?.sido_cd) {
    qs.set('sido_cd', params.sido_cd)
  }
  if (params?.bjdong_cd && params.bjdong_cd !== '00000') {
    qs.set('bjdong_cd', params.bjdong_cd)
  }
  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  return requestJson<DashboardSummaryResponse>(`${API_BASE}/dashboard${suffix}`)
}

export async function fetchMonthlyDashboard(
  params: MonthlyQueryParams = {},
): Promise<MonthlySummaryResponse> {
  const qs = new URLSearchParams()
  if (params.sigungu_cd) qs.set('sigungu_cd', params.sigungu_cd)
  if (params.bjdong_cd && params.bjdong_cd !== '00000') qs.set('bjdong_cd', params.bjdong_cd)
  if (params.months !== undefined) qs.set('months', String(params.months))
  if (params.month) qs.set('month', params.month)
  if (params.basis) qs.set('basis', params.basis)
  if (params.include_excluded !== undefined) {
    qs.set('include_excluded', String(params.include_excluded))
  }
  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  return requestJson<MonthlySummaryResponse>(`${API_BASE}/dashboard/monthly${suffix}`)
}

export async function fetchBuildings(
  params: BuildingSearchParams = {},
): Promise<PaginatedBuildingsResponse> {
  const qs = new URLSearchParams()
  if (params.sigungu_cd) {
    qs.set('sigungu_cd', params.sigungu_cd)
  } else if (params.sido_cd) {
    qs.set('sido_cd', params.sido_cd)
  }
  if (params.bjdong_cd && params.bjdong_cd !== '00000') qs.set('bjdong_cd', params.bjdong_cd)
  if (params.stages && params.stages.length > 0) {
    for (const stage of params.stages) {
      qs.append('stages', stage)
    }
  }
  if (params.scale && params.scale !== 'all') qs.set('scale', params.scale)
  if (params.main_purps) qs.set('main_purps', params.main_purps)
  if (params.min_hhld_cnt !== undefined) qs.set('min_hhld_cnt', String(params.min_hhld_cnt))
  if (params.min_tot_area !== undefined) qs.set('min_tot_area', String(params.min_tot_area))
  if (params.min_priority_score !== undefined) {
    qs.set('min_priority_score', String(params.min_priority_score))
  }
  if (params.date_from) qs.set('date_from', params.date_from)
  if (params.date_to) qs.set('date_to', params.date_to)
  if (params.q) qs.set('q', params.q)
  if (params.include_excluded !== undefined) {
    qs.set('include_excluded', String(params.include_excluded))
  }
  if (params.sort_by) qs.set('sort_by', params.sort_by)
  if (params.sort_order) qs.set('sort_order', params.sort_order)
  if (params.page !== undefined) qs.set('page', String(params.page))
  if (params.page_size !== undefined) qs.set('page_size', String(params.page_size))

  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  return requestJson<PaginatedBuildingsResponse>(`${API_BASE}/buildings${suffix}`)
}

export async function fetchBuildingDetail(pk: string): Promise<BuildingDetail> {
  return requestJson<BuildingDetail>(`${API_BASE}/buildings/${encodeURIComponent(pk)}`)
}

export async function syncBuildings(payload: BuildingSyncRequest): Promise<BuildingSyncResponse> {
  return requestJson<BuildingSyncResponse>(`${API_BASE}/buildings/sync`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function resetBuildings(
  sigunguCd?: string,
): Promise<{ deleted_buildings: number; sigungu_cd: string | null }> {
  const qs = new URLSearchParams()
  if (sigunguCd) qs.set('sigungu_cd', sigunguCd)
  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  return requestJson<{ deleted_buildings: number; sigungu_cd: string | null }>(
    `${API_BASE}/buildings/reset${suffix}`,
    { method: 'DELETE' },
  )
}

export async function createExclusion(
  payload: ExclusionCreateRequest,
): Promise<ExclusionHistoryItem> {
  return requestJson<ExclusionHistoryItem>(`${API_BASE}/exclusions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function restoreExclusion(
  pk: string,
  restoredBy: string,
): Promise<ExclusionHistoryItem> {
  return requestJson<ExclusionHistoryItem>(
    `${API_BASE}/exclusions/${encodeURIComponent(pk)}/restore`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ restored_by: restoredBy }),
    },
  )
}

export async function fetchExclusions(
  status?: ExclusionStatus,
  activeOnly = true,
): Promise<ExclusionListResponse> {
  const qs = new URLSearchParams()
  if (status) qs.set('status', status)
  qs.set('active_only', String(activeOnly))
  return requestJson<ExclusionListResponse>(`${API_BASE}/exclusions?${qs.toString()}`)
}

export async function fetchExclusionHistory(pk: string): Promise<ExclusionListResponse> {
  return requestJson<ExclusionListResponse>(
    `${API_BASE}/exclusions/${encodeURIComponent(pk)}/history`,
  )
}

export async function uploadExclusionCsv(
  file: File,
  actor: string,
  status: ExclusionStatus,
): Promise<ExclusionBulkResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('actor', actor)
  formData.append('status', status)

  return requestJson<ExclusionBulkResponse>(`${API_BASE}/exclusions/bulk-csv`, {
    method: 'POST',
    body: formData,
  })
}

export async function generateReport(payload: ReportGenerateRequest): Promise<ReportRunItem> {
  return requestJson<ReportRunItem>(`${API_BASE}/reports/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function getReportDownloadUrl(reportId: number, format: 'excel' | 'pdf'): string {
  return `${API_BASE}/reports/${reportId}/download?format=${format}`
}
