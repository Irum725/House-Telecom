import { CalendarDays } from 'lucide-react'
import type {
  BuildingSummary,
  ExclusionStatus,
  MonthlyDateBasis,
  MonthlySummaryResponse,
} from '../types/api'
import {
  BUILDING_STAGE_LABELS,
  EXCLUSION_ACTIONS,
  MONTHLY_BASIS_LABELS,
} from '../types/api'
import { formatArea, formatNumber, formatYmd } from '../utils/format'

interface MonthlyTabProps {
  data: MonthlySummaryResponse | null
  loading: boolean
  basis: MonthlyDateBasis
  monthsWindow: number
  selectedMonth: string
  includeExcluded: boolean
  selectedSigungu: string
  onBasisChange: (basis: MonthlyDateBasis) => void
  onMonthsWindowChange: (months: number) => void
  onSelectMonth: (month: string) => void
  onIncludeExcludedChange: (val: boolean) => void
  onSelectAction: (building: BuildingSummary, status: ExclusionStatus) => void
}

export function MonthlyTab({
  data,
  loading,
  basis,
  monthsWindow,
  selectedMonth,
  includeExcluded,
  selectedSigungu,
  onBasisChange,
  onMonthsWindowChange,
  onSelectMonth,
  onIncludeExcludedChange,
  onSelectAction,
}: MonthlyTabProps) {
  const months = data?.months ?? []
  const maxCount = Math.max(1, ...months.map((m) => m.total_count))
  const activeMonth = selectedMonth || data?.selected_month || ''
  const buildings = data?.buildings ?? []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <section className="card" aria-label="월별 신축 건물 조회 조건">
        <div className="card-header">
          <h2 className="card-title">
            <CalendarDays size={17} />
            월 단위 신축 건물 파악 {selectedSigungu ? `(시군구: ${selectedSigungu})` : '(전체 지역)'}
          </h2>
        </div>

        <div className="toolbar-row">
          <div className="field-group">
            <label className="field-label" htmlFor="monthly-basis">
              기준일
            </label>
            <select
              id="monthly-basis"
              className="select"
              value={basis}
              onChange={(e) => onBasisChange(e.target.value as MonthlyDateBasis)}
            >
              {(Object.keys(MONTHLY_BASIS_LABELS) as MonthlyDateBasis[]).map((key) => (
                <option key={key} value={key}>
                  {MONTHLY_BASIS_LABELS[key]}
                </option>
              ))}
            </select>
          </div>

          <div className="field-group">
            <label className="field-label" htmlFor="monthly-window">
              조회 기간
            </label>
            <select
              id="monthly-window"
              className="select"
              value={monthsWindow}
              onChange={(e) => onMonthsWindowChange(Number(e.target.value))}
            >
              <option value={6}>최근 6개월</option>
              <option value={12}>최근 12개월</option>
              <option value={24}>최근 24개월</option>
            </select>
          </div>

          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={includeExcluded}
              onChange={(e) => onIncludeExcludedChange(e.target.checked)}
            />
            제외 건축물 포함
          </label>
        </div>
      </section>

      <section className="card" aria-label="월별 집계 표">
        <div className="card-header">
          <h2 className="card-title">월별 신축 현황 (월을 클릭하면 상세 목록을 조회합니다)</h2>
          <span className="top20-meta">{months.length}개 월</span>
        </div>

        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>월 (YYYY-MM)</th>
                <th>총 건수</th>
                <th>분포</th>
                <th>건축허가</th>
                <th>착공예정</th>
                <th>착공진행</th>
                <th>준공임박</th>
                <th>사용승인</th>
                <th>총 세대수</th>
                <th>총 연면적</th>
              </tr>
            </thead>
            <tbody>
              {loading && months.length === 0 ? (
                <tr>
                  <td colSpan={10} className="empty-state">
                    월별 통계를 불러오는 중입니다...
                  </td>
                </tr>
              ) : months.length === 0 ? (
                <tr>
                  <td colSpan={10} className="empty-state">
                    해당 조건의 월별 신축 데이터가 없습니다.
                  </td>
                </tr>
              ) : (
                months.map((m) => {
                  const isSelected = m.month === activeMonth
                  const barPct = Math.round((m.total_count / maxCount) * 100)
                  return (
                    <tr
                      key={m.month}
                      data-testid={`monthly-row-${m.month}`}
                      onClick={() => onSelectMonth(m.month)}
                      style={{
                        cursor: 'pointer',
                        backgroundColor: isSelected ? 'var(--primary-soft)' : undefined,
                      }}
                    >
                      <td style={{ fontWeight: 700 }}>{m.month}</td>
                      <td style={{ fontWeight: 700 }}>{m.total_count.toLocaleString('ko-KR')}건</td>
                      <td style={{ minWidth: 110 }}>
                        <div
                          style={{
                            height: 8,
                            background: '#e2e8f0',
                            borderRadius: 999,
                            overflow: 'hidden',
                          }}
                        >
                          <div
                            style={{
                              width: `${barPct}%`,
                              height: '100%',
                              background: 'var(--primary)',
                            }}
                          />
                        </div>
                      </td>
                      <td>{m.permitted_count}</td>
                      <td>{m.start_scheduled_count}</td>
                      <td>{m.under_construction_count}</td>
                      <td>{m.near_completion_count}</td>
                      <td>{m.use_approved_count}</td>
                      <td>{formatNumber(m.total_hhld_cnt, '세대')}</td>
                      <td>{formatArea(m.total_tot_area)}</td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card" aria-label="선택 월 신축 건축물 상세">
        <div className="card-header">
          <h2 className="card-title">
            {activeMonth ? `${activeMonth} 신축 건축물 목록` : '선택된 월의 건축물 목록'}
          </h2>
          <span className="top20-meta">총 {(data?.total ?? buildings.length).toLocaleString()}건</span>
        </div>

        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>단계</th>
                <th>우선순위</th>
                <th>건축물 정보</th>
                <th>연면적 / 세대</th>
                <th>허가 / 착공 / 사용승인</th>
                <th>제외 처리</th>
              </tr>
            </thead>
            <tbody>
              {buildings.length === 0 ? (
                <tr>
                  <td colSpan={6} className="empty-state">
                    {activeMonth
                      ? `${activeMonth}에 해당하는 건축물이 없습니다.`
                      : '위 표에서 월을 선택하면 해당 월의 건축물 목록이 표시됩니다.'}
                  </td>
                </tr>
              ) : (
                buildings.map((b) => (
                  <tr key={b.mgm_pmsrgst_pk} data-testid={`monthly-building-${b.mgm_pmsrgst_pk}`}>
                    <td>
                      <span className={`badge badge-${b.stage}`}>
                        {BUILDING_STAGE_LABELS[b.stage]}
                      </span>
                    </td>
                    <td>
                      <span className={`score-pill ${b.priority_score >= 70 ? 'high' : ''}`}>
                        {Math.round(b.priority_score)}
                      </span>
                    </td>
                    <td>
                      <div style={{ fontWeight: 700 }}>{b.bld_nm || '(건물명 미상)'}</div>
                      <div className="top20-meta">{b.plat_plc || '-'}</div>
                      <div className="top20-meta">{b.main_purps_cd_nm || '-'}</div>
                    </td>
                    <td>
                      <div>{formatArea(b.tot_area)}</div>
                      <div className="top20-meta">
                        {formatNumber(b.hhld_cnt, '세대')} / {formatNumber(b.dong_cnt, '동')}
                      </div>
                    </td>
                    <td>
                      <div>허가: {formatYmd(b.arch_pms_day)}</div>
                      <div className="top20-meta">
                        착공: {formatYmd(b.real_stcns_day ?? b.stcns_sched_day)} · 승인:{' '}
                        {formatYmd(b.use_apr_day)}
                      </div>
                      {b.expected_completion_month && !b.use_apr_day && (
                        <div className="top20-meta">예상준공: {b.expected_completion_month}</div>
                      )}
                    </td>
                    <td>
                      <div className="action-btn-grid">
                        {EXCLUSION_ACTIONS.map((action) => (
                          <button
                            key={action.status}
                            type="button"
                            className="btn btn-sm"
                            onClick={() => onSelectAction(b, action.status)}
                          >
                            {action.label}
                          </button>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
