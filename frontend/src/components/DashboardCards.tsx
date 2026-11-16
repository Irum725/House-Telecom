import { Activity, AlertCircle } from 'lucide-react'
import type { BuildingStage, DashboardSummaryResponse } from '../types/api'
import { BUILDING_STAGE_LABELS, BUILDING_STAGE_ORDER } from '../types/api'
import { formatYmd } from '../utils/format'

interface DashboardCardsProps {
  dashboard: DashboardSummaryResponse | null
  selectedStages: BuildingStage[]
  onToggleStage: (stage: BuildingStage) => void
  loading?: boolean
}

export function DashboardCards({
  dashboard,
  selectedStages,
  onToggleStage,
  loading = false,
}: DashboardCardsProps) {
  const stageCountMap = new Map<BuildingStage, number>()
  for (const item of dashboard?.stage_counts ?? []) {
    stageCountMap.set(item.stage, item.count)
  }

  return (
    <section aria-label="대시보드 요약">
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-label">전체 건축물</div>
          <div className="kpi-value" data-testid="kpi-total">
            {loading && !dashboard ? '...' : (dashboard?.total_buildings ?? 0).toLocaleString()}
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">활성 영업 타겟</div>
          <div className="kpi-value" data-testid="kpi-active">
            {loading && !dashboard ? '...' : (dashboard?.active_targets ?? 0).toLocaleString()}
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">이번 달 신규 착공</div>
          <div className="kpi-value" data-testid="kpi-new-starts">
            {loading && !dashboard
              ? '...'
              : (dashboard?.new_starts_this_month ?? 0).toLocaleString()}
          </div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">제외 처리</div>
          <div className="kpi-value" data-testid="kpi-excluded">
            {loading && !dashboard ? '...' : (dashboard?.excluded_count ?? 0).toLocaleString()}
          </div>
        </div>
      </div>

      <div className="dashboard-split" style={{ marginTop: 14 }}>
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">
              <Activity size={17} />
              단계별 건수 (클릭하여 필터)
            </h2>
          </div>
          <div className="stage-grid">
            {BUILDING_STAGE_ORDER.map((stage) => {
              const count = stageCountMap.get(stage) ?? 0
              const isSelected = selectedStages.includes(stage)
              return (
                <button
                  key={stage}
                  type="button"
                  className={`stage-card-btn ${isSelected ? 'selected' : ''}`}
                  onClick={() => onToggleStage(stage)}
                  aria-pressed={isSelected}
                >
                  <div>
                    <span className={`badge badge-${stage}`}>{BUILDING_STAGE_LABELS[stage]}</span>
                  </div>
                  <div className="stage-card-count">{count.toLocaleString()}건</div>
                </button>
              )
            })}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h2 className="card-title">
              <AlertCircle size={17} />
              준공 임박 Top 20
            </h2>
            <span className="top20-meta">
              {(dashboard?.near_completion_top20 ?? []).length}건
            </span>
          </div>
          <div className="top20-list" data-testid="near-completion-top20">
            {(dashboard?.near_completion_top20 ?? []).length === 0 ? (
              <div className="empty-state" style={{ padding: '20px 8px' }}>
                준공 임박 대상 건축물이 없습니다.
              </div>
            ) : (
              (dashboard?.near_completion_top20 ?? []).map((b, idx) => (
                <div key={b.mgm_pmsrgst_pk} className="top20-item">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                    <span className="top20-rank">{idx + 1}</span>
                    <div style={{ minWidth: 0 }}>
                      <div className="top20-name">{b.bld_nm || b.plat_plc || b.mgm_pmsrgst_pk}</div>
                      <div className="top20-meta">
                        {b.plat_plc ?? '-'} · 착공 {formatYmd(b.real_stcns_day ?? b.stcns_sched_day)}
                        {b.expected_completion_month ? ` · 예상준공 ${b.expected_completion_month}` : ''}
                      </div>
                    </div>
                  </div>
                  <span className={`score-pill ${b.priority_score >= 70 ? 'high' : ''}`}>
                    {Math.round(b.priority_score)}점
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
