import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type {
  BuildingSummary,
  DashboardSummaryResponse,
  ExclusionHistoryItem,
  RegionItem,
} from './types/api'

const SIDO_LIST: RegionItem[] = [
  {
    code: '4100000000',
    sido_cd: '41',
    sigungu_cd: '41000',
    bjdong_cd: '00000',
    sido_name: '경기도',
    sigungu_name: null,
    emd_name: null,
    is_active: true,
  },
]

const SIGUNGU_LIST: RegionItem[] = [
  {
    code: '4113500000',
    sido_cd: '41',
    sigungu_cd: '41135',
    bjdong_cd: '00000',
    sido_name: '경기도',
    sigungu_name: '성남시 분당구',
    emd_name: null,
    is_active: true,
  },
]

const EMD_LIST: RegionItem[] = [
  {
    code: '4113510300',
    sido_cd: '41',
    sigungu_cd: '41135',
    bjdong_cd: '10300',
    sido_name: '경기도',
    sigungu_name: '성남시 분당구',
    emd_name: '정자동',
    is_active: true,
  },
]

const SAMPLE_BUILDING: BuildingSummary = {
  mgm_pmsrgst_pk: '41135-2026-001',
  bld_rgst_pk: null,
  sigungu_cd: '41135',
  bjdong_cd: '10300',
  plat_plc: '경기도 성남시 분당구 정자동 100',
  bld_nm: '분당 테크타워',
  main_purps_cd_nm: '업무시설',
  tot_area: 12500.5,
  hhld_cnt: 0,
  dong_cnt: 1,
  arch_pms_day: '20260115',
  stcns_sched_day: '20260301',
  real_stcns_day: '20260305',
  use_apr_day: null,
  stage: 'NEAR_COMPLETION',
  priority_score: 88,
  is_excluded: false,
  active_exclusion_status: null,
  expected_completion_month: '2027-01',
}

const SAMPLE_DASHBOARD: DashboardSummaryResponse = {
  total_buildings: 12,
  active_targets: 10,
  excluded_count: 2,
  new_starts_this_month: 3,
  stage_counts: [
    { stage: 'PERMITTED', count: 2 },
    { stage: 'START_SCHEDULED', count: 3 },
    { stage: 'UNDER_CONSTRUCTION', count: 4 },
    { stage: 'NEAR_COMPLETION', count: 1 },
    { stage: 'USE_APPROVED', count: 0 },
  ],
  exclusion_counts: [{ status: 'TELECOM_DONE_FIELD', count: 2 }],
  near_completion_top20: [SAMPLE_BUILDING],
  top_priority_buildings: [SAMPLE_BUILDING],
  recent_reports: [],
  api_traffic_today: 42,
  api_daily_limit: 10000,
}

const SAMPLE_EXCLUSION: ExclusionHistoryItem = {
  id: 1,
  mgm_pmsrgst_pk: '41135-2026-099',
  actor: '김영업',
  created_at: '2026-11-15T09:30:00Z',
  status: 'TELECOM_DONE_FIELD',
  reason: '현장 개통 확인 완료',
  evidence: '/photos/site01.jpg',
  is_active: true,
  restored_at: null,
  restored_by: null,
}

function jsonResponse(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('신축 통신공사 사전파악 리포트 시스템 UI', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString()
      const method = init?.method ?? 'GET'

      if (url.startsWith('/api/regions/sido')) {
        return jsonResponse({ items: SIDO_LIST, total: SIDO_LIST.length })
      }
      if (url.startsWith('/api/regions/sigungu')) {
        return jsonResponse({ items: SIGUNGU_LIST, total: SIGUNGU_LIST.length })
      }
      if (url.startsWith('/api/regions/emd')) {
        return jsonResponse({ items: EMD_LIST, total: EMD_LIST.length })
      }
      if (url.startsWith('/api/dashboard/monthly')) {
        const parsed = new URL(url, 'http://localhost')
        const month = parsed.searchParams.get('month') ?? '2026-11'
        return jsonResponse({
          months: [
            {
              month: '2026-11',
              permitted_count: 1,
              start_scheduled_count: 1,
              under_construction_count: 2,
              near_completion_count: 1,
              use_approved_count: 0,
              total_count: 5,
              total_hhld_cnt: 120,
              total_tot_area: 15000,
            },
            {
              month: '2026-10',
              permitted_count: 2,
              start_scheduled_count: 0,
              under_construction_count: 1,
              near_completion_count: 0,
              use_approved_count: 1,
              total_count: 4,
              total_hhld_cnt: 80,
              total_tot_area: 9000,
            },
          ],
          selected_month: month,
          buildings: [SAMPLE_BUILDING],
          total: 1,
        })
      }
      if (url.startsWith('/api/dashboard')) {
        return jsonResponse(SAMPLE_DASHBOARD)
      }
      if (url.startsWith('/api/buildings/sync') && method === 'POST') {
        return jsonResponse({
          sigungu_cd: '41135',
          bjdong_cd: '10300',
          fetched_count: 5,
          created_count: 5,
          updated_count: 0,
          api_calls_used: 0,
          remaining_daily_quota: 10000,
        })
      }
      if (url.startsWith('/api/buildings')) {
        return jsonResponse({
          items: [SAMPLE_BUILDING],
          total: 1,
          page: 1,
          page_size: 20,
          total_pages: 1,
        })
      }
      if (url === '/api/exclusions' && method === 'POST') {
        return jsonResponse(SAMPLE_EXCLUSION, 201)
      }
      if (url.startsWith('/api/exclusions/bulk-csv') && method === 'POST') {
        return jsonResponse({
          total_rows: 1,
          excluded_count: 1,
          not_found_count: 0,
          error_count: 0,
          results: [
            {
              row_number: 1,
              identifier: '41135-2026-001',
              matched_pk: '41135-2026-001',
              status: 'excluded',
              detail: null,
            },
          ],
        })
      }
      if (url.includes('/restore') && method === 'POST') {
        return jsonResponse({ ...SAMPLE_EXCLUSION, is_active: false, restored_by: '관리자' })
      }
      if (url.startsWith('/api/exclusions')) {
        return jsonResponse({ items: [SAMPLE_EXCLUSION], total: 1 })
      }
      if (url.startsWith('/api/reports/generate') && method === 'POST') {
        return jsonResponse(
          {
            id: 7,
            region_code: '4113500000',
            run_at: '2026-11-16T10:00:00Z',
            excel_path: 'reports/r.xlsx',
            pdf_path: 'reports/r.pdf',
            total_count: 1,
            new_count: 1,
            stage_changed_count: 0,
            diff_json: null,
          },
          201,
        )
      }

      return jsonResponse({ detail: `Unhandled mock: ${method} ${url}` }, 404)
    })

    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders dashboard KPIs, stage counts, and near-completion Top 20', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByTestId('kpi-total')).toHaveTextContent('12')
    })
    expect(screen.getByTestId('kpi-new-starts')).toHaveTextContent('3')
    expect(screen.getByTestId('kpi-excluded')).toHaveTextContent('2')
    const top20 = screen.getByTestId('near-completion-top20')
    expect(within(top20).getByText('분당 테크타워')).toBeInTheDocument()
    const row = await screen.findByTestId('building-row-41135-2026-001')
    expect(within(row).getByText('예상준공: 2027-01')).toBeInTheDocument()
  })

  it('supports 3-step region selection, fixture data collection, and Excel/PDF report generation', async () => {
    const user = userEvent.setup()
    render(<App />)

    const sidoSelect = await screen.findByLabelText('1. 시/도')
    await waitFor(() => expect(within(sidoSelect).getByText('경기도')).toBeInTheDocument())
    await user.selectOptions(sidoSelect, '41')

    const sigunguSelect = screen.getByLabelText('2. 시/군/구')
    await waitFor(() =>
      expect(within(sigunguSelect).getByText('성남시 분당구')).toBeInTheDocument(),
    )
    await user.selectOptions(sigunguSelect, '41135')

    const emdSelect = screen.getByLabelText('3. 읍/면/동 (선택)')
    await waitFor(() => expect(within(emdSelect).getByText('정자동')).toBeInTheDocument())
    await user.selectOptions(emdSelect, '10300')

    await user.click(screen.getByRole('button', { name: /데이터 수집/ }))
    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent('수집 완료: 조회 5건')
    })

    await user.click(screen.getByRole('button', { name: /Excel/ }))
    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent('Excel 리포트 생성 완료')
    })

    await user.click(screen.getByRole('button', { name: /PDF/ }))
    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent('PDF 리포트 생성 완료')
    })
  })

  it('opens exclusion modal on row action and submits exclusion with reason & evidence', async () => {
    const user = userEvent.setup()
    render(<App />)

    const row = await screen.findByTestId('building-row-41135-2026-001')
    await user.click(within(row).getByRole('button', { name: '통신공사 완료(실사)' }))

    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByText('제외 사유 및 증빙 등록')).toBeInTheDocument()

    await user.type(within(dialog).getByLabelText('사유'), '현장 실사 결과 개통 완료')
    await user.type(within(dialog).getByLabelText('증빙 메모 / 사진 경로'), '/photos/test.jpg')
    await user.click(within(dialog).getByRole('button', { name: '제외 확정' }))

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent('제외 처리가 완료되었습니다')
    })
  })

  it('shows excluded list tab with restore and CSV bulk upload', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /제외 목록 \/ 일괄 관리/ }))

    const exclRow = await screen.findByTestId('excluded-row-41135-2026-099')
    expect(within(exclRow).getByText('현장 개통 확인 완료')).toBeInTheDocument()

    await user.click(within(exclRow).getByRole('button', { name: '복원' }))
    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent('타겟 목록으로 복원되었습니다')
    })

    const file = new File(['mgm_pmsrgst_pk,reason\n41135-2026-001,bulk'], 'bulk.csv', {
      type: 'text/csv',
    })
    await user.upload(screen.getByLabelText('CSV 파일'), file)
    await user.click(screen.getByRole('button', { name: /CSV 일괄 업로드/ }))

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent('CSV 일괄 처리 완료: 1건 제외됨')
    })
  })

  it('displays monthly new building tracking tab and supports month & basis selection', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /월별 신축 파악/ }))

    const novRow = await screen.findByTestId('monthly-row-2026-11')
    expect(within(novRow).getByText('5건')).toBeInTheDocument()
    expect(screen.getByTestId('monthly-building-41135-2026-001')).toBeInTheDocument()

    const octRow = screen.getByTestId('monthly-row-2026-10')
    await user.click(octRow)
    await waitFor(() => {
      expect(screen.getByText('2026-10 신축 건축물 목록')).toBeInTheDocument()
    })

    await user.selectOptions(screen.getByLabelText('기준일'), 'use_apr_day')
    await waitFor(() => {
      const calls = fetchMock.mock.calls.map(([u]) => String(u))
      expect(calls.some((u) => u.includes('/api/dashboard/monthly') && u.includes('basis=use_apr_day'))).toBe(true)
    })
  })

  it('filters buildings by scale (small/large)', async () => {
    const user = userEvent.setup()
    render(<App />)

    const scaleSelect = await screen.findByLabelText('건축물 규모')
    await user.selectOptions(scaleSelect, 'small')

    await waitFor(() => {
      const calls = fetchMock.mock.calls.map(([u]) => String(u))
      expect(calls.some((u) => u.includes('/api/buildings') && u.includes('scale=small'))).toBe(true)
    })
  })

  it('resets collected buildings when clicking 데이터 초기화 after confirm', async () => {
    const user = userEvent.setup()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<App />)

    const resetBtn = await screen.findByRole('button', { name: /데이터 초기화/ })
    await user.click(resetBtn)

    await waitFor(() => {
      const calls = fetchMock.mock.calls.map(([u, init]) => ({
        url: String(u),
        method: (init as RequestInit | undefined)?.method ?? 'GET',
      }))
      expect(calls.some((c) => c.url.includes('/api/buildings/reset') && c.method === 'DELETE')).toBe(true)
    })
  })

  it('defaults dateFrom to Jan 1 of current year and dateTo to Dec 31 of next year', async () => {
    render(<App />)
    const year = new Date().getFullYear()
    const expectedFrom = `${year}-01-01`
    const expectedTo = `${year + 1}-12-31`

    const fromInput = (await screen.findByLabelText('허가/착공 시작일')) as HTMLInputElement
    const toInput = (await screen.findByLabelText('허가/착공 종료일')) as HTMLInputElement

    expect(fromInput.value).toBe(expectedFrom)
    expect(toInput.value).toBe(expectedTo)

    await waitFor(() => {
      const calls = fetchMock.mock.calls.map(([u]) => String(u))
      expect(
        calls.some(
          (u) =>
            u.includes('/api/buildings') &&
            u.includes(`date_from=${year}0101`) &&
            u.includes(`date_to=${year + 1}1231`),
        ),
      ).toBe(true)
    })
  })
})
