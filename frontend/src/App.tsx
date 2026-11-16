import { useCallback, useEffect, useState } from 'react'
import {
  createExclusion,
  fetchBuildings,
  fetchDashboard,
  fetchEmd,
  fetchExclusionHistory,
  fetchExclusions,
  fetchHealth,
  fetchMonthlyDashboard,
  fetchSido,
  fetchSigungu,
  generateReport,
  getReportDownloadUrl,
  restoreExclusion,
  syncBuildings,
  uploadExclusionCsv,
} from './api/client'
import { BuildingsTable } from './components/BuildingsTable'
import { DashboardCards } from './components/DashboardCards'
import { ExcludedTab } from './components/ExcludedTab'
import { ExclusionModal } from './components/ExclusionModal'
import { FilterBar, type FilterState } from './components/FilterBar'
import { Header, type ActiveTab } from './components/Header'
import { MonthlyTab } from './components/MonthlyTab'
import { RegionCollectorBar } from './components/RegionCollectorBar'
import type {
  BuildingSortBy,
  BuildingStage,
  BuildingSummary,
  DashboardSummaryResponse,
  ExclusionBulkResponse,
  ExclusionHistoryItem,
  ExclusionStatus,
  MonthlyDateBasis,
  MonthlySummaryResponse,
  PaginatedBuildingsResponse,
  RegionItem,
  SortOrder,
} from './types/api'

const INITIAL_FILTERS: FilterState = {
  stages: [],
  scale: 'all',
  mainPurps: '',
  minScore: '',
  dateFrom: '',
  dateTo: '',
  q: '',
}

export function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('targets')

  // Region 3-step state
  const [sidoList, setSidoList] = useState<RegionItem[]>([])
  const [sigunguList, setSigunguList] = useState<RegionItem[]>([])
  const [emdList, setEmdList] = useState<RegionItem[]>([])
  const [selectedSido, setSelectedSido] = useState('')
  const [selectedSigungu, setSelectedSigungu] = useState('')
  const [selectedEmd, setSelectedEmd] = useState('00000')
  const [useFixture, setUseFixture] = useState(true)

  // Dashboard & Buildings state
  const [dashboard, setDashboard] = useState<DashboardSummaryResponse | null>(null)
  const [dashboardLoading, setDashboardLoading] = useState(false)
  const [buildingsData, setBuildingsData] = useState<PaginatedBuildingsResponse>({
    items: [],
    total: 0,
    page: 1,
    page_size: 20,
    total_pages: 1,
  })
  const [buildingsLoading, setBuildingsLoading] = useState(false)

  // Filters, sort, pagination
  const [filters, setFilters] = useState<FilterState>(INITIAL_FILTERS)
  const [sortBy, setSortBy] = useState<BuildingSortBy>('priority_score')
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc')
  const [page, setPage] = useState(1)

  // Actions & Feedback
  const [syncing, setSyncing] = useState(false)
  const [exportingFormat, setExportingFormat] = useState<'excel' | 'pdf' | null>(null)
  const [notice, setNotice] = useState<{ type: 'success' | 'error' | 'info'; text: string } | null>(
    null,
  )

  // Exclusion modal
  const [modalTarget, setModalTarget] = useState<{
    building: BuildingSummary
    status: ExclusionStatus
  } | null>(null)
  const [submittingExclusion, setSubmittingExclusion] = useState(false)

  // Excluded tab state
  const [exclusions, setExclusions] = useState<ExclusionHistoryItem[]>([])
  const [exclusionsLoading, setExclusionsLoading] = useState(false)
  const [exclStatusFilter, setExclStatusFilter] = useState<ExclusionStatus | ''>('')
  const [exclActiveOnly, setExclActiveOnly] = useState(true)
  const [historyTargetPk, setHistoryTargetPk] = useState<string | null>(null)
  const [historyItems, setHistoryItems] = useState<ExclusionHistoryItem[]>([])
  const [bulkResult, setBulkResult] = useState<ExclusionBulkResponse | null>(null)
  const [uploadingCsv, setUploadingCsv] = useState(false)
  const [restoringPk, setRestoringPk] = useState<string | null>(null)

  // Monthly tab state
  const [monthlyData, setMonthlyData] = useState<MonthlySummaryResponse | null>(null)
  const [monthlyLoading, setMonthlyLoading] = useState(false)
  const [monthlyBasis, setMonthlyBasis] = useState<MonthlyDateBasis>('all')
  const [monthlyWindow, setMonthlyWindow] = useState(12)
  const [selectedMonth, setSelectedMonth] = useState('')
  const [monthlyIncludeExcluded, setMonthlyIncludeExcluded] = useState(false)

  const loadDashboard = useCallback(async () => {
    setDashboardLoading(true)
    try {
      const data = await fetchDashboard(selectedSigungu || undefined)
      setDashboard(data)
    } catch (err) {
      setNotice({
        type: 'error',
        text: err instanceof Error ? err.message : '대시보드 조회 중 오류가 발생했습니다.',
      })
    } finally {
      setDashboardLoading(false)
    }
  }, [selectedSigungu])

  const loadBuildings = useCallback(async () => {
    setBuildingsLoading(true)
    try {
      const minScoreNum = filters.minScore.trim() ? Number(filters.minScore) : undefined
      const data = await fetchBuildings({
        sigungu_cd: selectedSigungu || undefined,
        bjdong_cd: selectedEmd && selectedEmd !== '00000' ? selectedEmd : undefined,
        stages: filters.stages.length > 0 ? filters.stages : undefined,
        scale: filters.scale !== 'all' ? filters.scale : undefined,
        main_purps: filters.mainPurps.trim() || undefined,
        min_priority_score:
          minScoreNum !== undefined && !Number.isNaN(minScoreNum) ? minScoreNum : undefined,
        date_from: filters.dateFrom ? filters.dateFrom.replace(/-/g, '') : undefined,
        date_to: filters.dateTo ? filters.dateTo.replace(/-/g, '') : undefined,
        q: filters.q.trim() || undefined,
        include_excluded: false,
        sort_by: sortBy,
        sort_order: sortOrder,
        page,
        page_size: 20,
      })
      setBuildingsData(data)
    } catch (err) {
      setNotice({
        type: 'error',
        text: err instanceof Error ? err.message : '건축물 목록 조회 중 오류가 발생했습니다.',
      })
    } finally {
      setBuildingsLoading(false)
    }
  }, [selectedSigungu, selectedEmd, filters, sortBy, sortOrder, page])

  const loadExclusions = useCallback(async () => {
    setExclusionsLoading(true)
    try {
      const data = await fetchExclusions(exclStatusFilter || undefined, exclActiveOnly)
      setExclusions(data.items)
    } catch (err) {
      setNotice({
        type: 'error',
        text: err instanceof Error ? err.message : '제외 목록 조회 중 오류가 발생했습니다.',
      })
    } finally {
      setExclusionsLoading(false)
    }
  }, [exclStatusFilter, exclActiveOnly])

  const loadMonthly = useCallback(async () => {
    setMonthlyLoading(true)
    try {
      const data = await fetchMonthlyDashboard({
        sigungu_cd: selectedSigungu || undefined,
        bjdong_cd: selectedEmd && selectedEmd !== '00000' ? selectedEmd : undefined,
        months: monthlyWindow,
        month: selectedMonth || undefined,
        basis: monthlyBasis,
        include_excluded: monthlyIncludeExcluded,
      })
      setMonthlyData(data)
    } catch (err) {
      setNotice({
        type: 'error',
        text: err instanceof Error ? err.message : '월별 통계 조회 중 오류가 발생했습니다.',
      })
    } finally {
      setMonthlyLoading(false)
    }
  }, [
    selectedSigungu,
    selectedEmd,
    monthlyWindow,
    selectedMonth,
    monthlyBasis,
    monthlyIncludeExcluded,
  ])

  useEffect(() => {
    fetchHealth()
      .then((res) => {
        if (res.live_api_configured) {
          setUseFixture(false)
        }
      })
      .catch(() => {})
    fetchSido()
      .then((res) => setSidoList(res.items))
      .catch((err) =>
        setNotice({
          type: 'error',
          text: err instanceof Error ? err.message : '시/도 목록 조회 실패',
        }),
      )
  }, [])

  useEffect(() => {
    void loadDashboard()
  }, [loadDashboard])

  useEffect(() => {
    void loadBuildings()
  }, [loadBuildings])

  useEffect(() => {
    void loadExclusions()
  }, [loadExclusions])

  useEffect(() => {
    if (activeTab === 'monthly') {
      void loadMonthly()
    }
  }, [activeTab, loadMonthly])

  const handleSidoChange = async (sidoCd: string) => {
    setSelectedSido(sidoCd)
    setSelectedSigungu('')
    setSelectedEmd('00000')
    setSigunguList([])
    setEmdList([])
    setPage(1)
    if (!sidoCd) return
    try {
      const res = await fetchSigungu(sidoCd)
      setSigunguList(res.items)
    } catch (err) {
      setNotice({
        type: 'error',
        text: err instanceof Error ? err.message : '시/군/구 목록 조회 실패',
      })
    }
  }

  const handleSigunguChange = async (sigunguCd: string) => {
    setSelectedSigungu(sigunguCd)
    setSelectedEmd('00000')
    setEmdList([])
    setPage(1)
    if (!sigunguCd) return
    try {
      const res = await fetchEmd(sigunguCd)
      setEmdList(res.items)
    } catch (err) {
      setNotice({
        type: 'error',
        text: err instanceof Error ? err.message : '읍/면/동 목록 조회 실패',
      })
    }
  }

  const handleEmdChange = (bjdongCd: string) => {
    setSelectedEmd(bjdongCd || '00000')
    setPage(1)
  }

  const handleCollect = async () => {
    if (!selectedSigungu) return
    setSyncing(true)
    setNotice(null)
    try {
      const res = await syncBuildings({
        sigungu_cd: selectedSigungu,
        bjdong_cd: selectedEmd || '00000',
        use_fixture: useFixture,
      })
      setNotice({
        type: 'success',
        text: `수집 완료: 조회 ${res.fetched_count}건 (신규 ${res.created_count}건, 갱신 ${res.updated_count}건)`,
      })
      setPage(1)
      await Promise.all([loadDashboard(), loadBuildings()])
    } catch (err) {
      setNotice({
        type: 'error',
        text: err instanceof Error ? err.message : '데이터 수집 중 오류가 발생했습니다.',
      })
    } finally {
      setSyncing(false)
    }
  }

  const handleDownloadReport = async (format: 'excel' | 'pdf') => {
    if (!selectedSigungu) return
    setExportingFormat(format)
    setNotice(null)
    try {
      const report = await generateReport({
        sigungu_cd: selectedSigungu,
        bjdong_cd: selectedEmd || '00000',
        stages: filters.stages.length > 0 ? filters.stages : undefined,
        include_excluded: false,
        formats: [format],
      })
      const url = getReportDownloadUrl(report.id, format)
      const link = document.createElement('a')
      link.href = url
      link.download = `report_${report.region_code}.${format === 'excel' ? 'xlsx' : 'pdf'}`
      document.body.appendChild(link)
      link.click()
      link.remove()
      setNotice({
        type: 'success',
        text: `${format === 'excel' ? 'Excel' : 'PDF'} 리포트 생성 완료 (총 ${report.total_count}건)`,
      })
    } catch (err) {
      setNotice({
        type: 'error',
        text: err instanceof Error ? err.message : '리포트 생성 중 오류가 발생했습니다.',
      })
    } finally {
      setExportingFormat(null)
    }
  }

  const handleToggleStage = (stage: BuildingStage) => {
    setPage(1)
    setFilters((prev) => {
      const exists = prev.stages.includes(stage)
      return {
        ...prev,
        stages: exists ? prev.stages.filter((s) => s !== stage) : [...prev.stages, stage],
      }
    })
  }

  const handleSortChange = (field: BuildingSortBy) => {
    setPage(1)
    if (sortBy === field) {
      setSortOrder((prev) => (prev === 'desc' ? 'asc' : 'desc'))
    } else {
      setSortBy(field)
      setSortOrder('desc')
    }
  }

  const handleExclusionSubmit = async (payload: {
    mgm_pmsrgst_pk: string
    status: ExclusionStatus
    actor: string
    reason: string
    evidence: string
  }) => {
    setSubmittingExclusion(true)
    try {
      await createExclusion({
        mgm_pmsrgst_pk: payload.mgm_pmsrgst_pk,
        actor: payload.actor,
        status: payload.status,
        reason: payload.reason || null,
        evidence: payload.evidence || null,
      })
      setModalTarget(null)
      setNotice({
        type: 'success',
        text: `제외 처리가 완료되었습니다 (${payload.mgm_pmsrgst_pk}).`,
      })
      await Promise.all([loadDashboard(), loadBuildings(), loadExclusions()])
    } catch (err) {
      setNotice({
        type: 'error',
        text: err instanceof Error ? err.message : '제외 처리 중 오류가 발생했습니다.',
      })
    } finally {
      setSubmittingExclusion(false)
    }
  }

  const handleRestore = async (pk: string, restoredBy: string) => {
    setRestoringPk(pk)
    try {
      await restoreExclusion(pk, restoredBy)
      setNotice({ type: 'success', text: `건축물(${pk})이 타겟 목록으로 복원되었습니다.` })
      await Promise.all([loadExclusions(), loadDashboard(), loadBuildings()])
    } catch (err) {
      setNotice({
        type: 'error',
        text: err instanceof Error ? err.message : '복원 중 오류가 발생했습니다.',
      })
    } finally {
      setRestoringPk(null)
    }
  }

  const handleViewHistory = async (pk: string) => {
    try {
      const res = await fetchExclusionHistory(pk)
      setHistoryItems(res.items)
      setHistoryTargetPk(pk)
    } catch (err) {
      setNotice({
        type: 'error',
        text: err instanceof Error ? err.message : '이력 조회 중 오류가 발생했습니다.',
      })
    }
  }

  const handleUploadCsv = async (file: File, actor: string, status: ExclusionStatus) => {
    setUploadingCsv(true)
    setBulkResult(null)
    try {
      const res = await uploadExclusionCsv(file, actor, status)
      setBulkResult(res)
      setNotice({
        type: 'success',
        text: `CSV 일괄 처리 완료: ${res.excluded_count}건 제외됨`,
      })
      await Promise.all([loadExclusions(), loadDashboard(), loadBuildings()])
    } catch (err) {
      setNotice({
        type: 'error',
        text: err instanceof Error ? err.message : 'CSV 업로드 중 오류가 발생했습니다.',
      })
    } finally {
      setUploadingCsv(false)
    }
  }

  return (
    <div className="app-shell">
      <Header
        activeTab={activeTab}
        onTabChange={setActiveTab}
        excludedCount={dashboard?.excluded_count ?? exclusions.filter((e) => e.is_active).length}
        apiTrafficToday={dashboard?.api_traffic_today}
        apiDailyLimit={dashboard?.api_daily_limit}
      />

      <main className="main-content">
        {notice && (
          <div className={`alert alert-${notice.type}`} role="status">
            <span>{notice.text}</span>
            <button type="button" className="btn btn-sm" onClick={() => setNotice(null)}>
              닫기
            </button>
          </div>
        )}

        <DashboardCards
          dashboard={dashboard}
          selectedStages={filters.stages}
          onToggleStage={handleToggleStage}
          loading={dashboardLoading}
        />

        {activeTab === 'targets' ? (
          <>
            <RegionCollectorBar
              sidoList={sidoList}
              sigunguList={sigunguList}
              emdList={emdList}
              selectedSido={selectedSido}
              selectedSigungu={selectedSigungu}
              selectedEmd={selectedEmd}
              useFixture={useFixture}
              syncing={syncing}
              exportingFormat={exportingFormat}
              onSidoChange={handleSidoChange}
              onSigunguChange={handleSigunguChange}
              onEmdChange={handleEmdChange}
              onUseFixtureChange={setUseFixture}
              onCollect={handleCollect}
              onDownloadReport={handleDownloadReport}
            />

            <FilterBar
              filters={filters}
              onChange={(next) => {
                setPage(1)
                setFilters(next)
              }}
              onReset={() => {
                setPage(1)
                setFilters(INITIAL_FILTERS)
              }}
            />

            <BuildingsTable
              items={buildingsData.items}
              total={buildingsData.total}
              page={buildingsData.page}
              totalPages={buildingsData.total_pages}
              sortBy={sortBy}
              sortOrder={sortOrder}
              loading={buildingsLoading}
              onSortChange={handleSortChange}
              onPageChange={setPage}
              onSelectAction={(building, status) => setModalTarget({ building, status })}
            />
          </>
        ) : activeTab === 'monthly' ? (
          <MonthlyTab
            data={monthlyData}
            loading={monthlyLoading}
            basis={monthlyBasis}
            monthsWindow={monthlyWindow}
            selectedMonth={selectedMonth}
            includeExcluded={monthlyIncludeExcluded}
            selectedSigungu={selectedSigungu}
            onBasisChange={(nextBasis) => {
              setSelectedMonth('')
              setMonthlyBasis(nextBasis)
            }}
            onMonthsWindowChange={(nextWindow) => {
              setSelectedMonth('')
              setMonthlyWindow(nextWindow)
            }}
            onSelectMonth={setSelectedMonth}
            onIncludeExcludedChange={setMonthlyIncludeExcluded}
            onSelectAction={(building, status) => setModalTarget({ building, status })}
          />
        ) : (
          <ExcludedTab
            items={exclusions}
            loading={exclusionsLoading}
            statusFilter={exclStatusFilter}
            activeOnly={exclActiveOnly}
            historyTargetPk={historyTargetPk}
            historyItems={historyItems}
            bulkResult={bulkResult}
            uploadingCsv={uploadingCsv}
            restoringPk={restoringPk}
            onStatusFilterChange={setExclStatusFilter}
            onActiveOnlyChange={setExclActiveOnly}
            onRestore={handleRestore}
            onViewHistory={handleViewHistory}
            onCloseHistory={() => setHistoryTargetPk(null)}
            onUploadCsv={handleUploadCsv}
          />
        )}
      </main>

      {modalTarget && (
        <ExclusionModal
          building={modalTarget.building}
          initialStatus={modalTarget.status}
          submitting={submittingExclusion}
          onClose={() => setModalTarget(null)}
          onSubmit={handleExclusionSubmit}
        />
      )}
    </div>
  )
}

export default App
