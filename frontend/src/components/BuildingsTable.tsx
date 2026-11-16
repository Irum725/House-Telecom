import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight } from 'lucide-react'
import type {
  BuildingSortBy,
  BuildingSummary,
  ExclusionStatus,
  SortOrder,
} from '../types/api'
import { BUILDING_STAGE_LABELS, EXCLUSION_ACTIONS } from '../types/api'
import { formatArea, formatNumber, formatYmd } from '../utils/format'

interface BuildingsTableProps {
  items: BuildingSummary[]
  total: number
  page: number
  totalPages: number
  sortBy: BuildingSortBy
  sortOrder: SortOrder
  loading?: boolean
  onSortChange: (field: BuildingSortBy) => void
  onPageChange: (page: number) => void
  onSelectAction: (building: BuildingSummary, status: ExclusionStatus) => void
}

function SortIcon({
  field,
  activeField,
  order,
}: {
  field: BuildingSortBy
  activeField: BuildingSortBy
  order: SortOrder
}) {
  if (field !== activeField) return <ArrowUpDown size={13} />
  return order === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />
}

export function BuildingsTable({
  items,
  total,
  page,
  totalPages,
  sortBy,
  sortOrder,
  loading = false,
  onSortChange,
  onPageChange,
  onSelectAction,
}: BuildingsTableProps) {
  return (
    <section className="card" aria-label="건축물 목록">
      <div className="card-header">
        <h2 className="card-title">타겟 건축물 목록</h2>
        <span className="top20-meta">총 {total.toLocaleString('ko-KR')}건</span>
      </div>

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>단계</th>
              <th>
                <button
                  type="button"
                  className="sort-btn"
                  onClick={() => onSortChange('priority_score')}
                >
                  우선순위
                  <SortIcon field="priority_score" activeField={sortBy} order={sortOrder} />
                </button>
              </th>
              <th>건축물 정보</th>
              <th>
                <button
                  type="button"
                  className="sort-btn"
                  onClick={() => onSortChange('tot_area')}
                >
                  연면적 / 세대
                  <SortIcon field="tot_area" activeField={sortBy} order={sortOrder} />
                </button>
              </th>
              <th>
                <button
                  type="button"
                  className="sort-btn"
                  onClick={() => onSortChange('arch_pms_day')}
                >
                  허가 / 착공일
                  <SortIcon field="arch_pms_day" activeField={sortBy} order={sortOrder} />
                </button>
              </th>
              <th>
                <button
                  type="button"
                  className="sort-btn"
                  onClick={() => onSortChange('use_apr_day')}
                >
                  사용승인 / 예상준공
                  <SortIcon field="use_apr_day" activeField={sortBy} order={sortOrder} />
                </button>
              </th>
              <th>제외 처리</th>
            </tr>
          </thead>
          <tbody>
            {loading && items.length === 0 ? (
              <tr>
                <td colSpan={7} className="empty-state">
                  데이터를 불러오는 중입니다...
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={7} className="empty-state">
                  조건에 맞는 건축물이 없습니다. 상단에서 지역을 선택해 데이터를 수집하거나 필터를 조정하세요.
                </td>
              </tr>
            ) : (
              items.map((b) => (
                <tr key={b.mgm_pmsrgst_pk} data-testid={`building-row-${b.mgm_pmsrgst_pk}`}>
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
                    <div style={{ fontWeight: 700 }}>
                      {b.bld_nm || (b.plat_plc ? `${b.plat_plc} 신축` : '(건물명 미상)')}
                    </div>
                    <div className="top20-meta">{b.plat_plc || '-'}</div>
                    <div className="top20-meta">
                      {b.main_purps_cd_nm || '-'} · PK: {b.mgm_pmsrgst_pk}
                    </div>
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
                      착공예정: {formatYmd(b.stcns_sched_day)}
                    </div>
                    <div className="top20-meta">
                      실착공: {formatYmd(b.real_stcns_day)}
                    </div>
                  </td>
                  <td>
                    <div>{formatYmd(b.use_apr_day)}</div>
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
                          title={action.label}
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

      <div className="pagination-bar">
        <span>
          페이지 {page} / {Math.max(1, totalPages)}
        </span>
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            type="button"
            className="btn btn-sm"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
          >
            <ChevronLeft size={14} />
            이전
          </button>
          <button
            type="button"
            className="btn btn-sm"
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
          >
            다음
            <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </section>
  )
}
