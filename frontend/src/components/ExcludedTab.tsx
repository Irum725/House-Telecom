import { useState } from 'react'
import { History, RotateCcw, Upload } from 'lucide-react'
import type {
  ExclusionBulkResponse,
  ExclusionHistoryItem,
  ExclusionStatus,
} from '../types/api'
import { EXCLUSION_STATUS_LABELS } from '../types/api'
import { formatIsoDateTime } from '../utils/format'

interface ExcludedTabProps {
  items: ExclusionHistoryItem[]
  loading: boolean
  statusFilter: ExclusionStatus | ''
  activeOnly: boolean
  historyTargetPk: string | null
  historyItems: ExclusionHistoryItem[]
  bulkResult: ExclusionBulkResponse | null
  uploadingCsv: boolean
  restoringPk: string | null
  onStatusFilterChange: (status: ExclusionStatus | '') => void
  onActiveOnlyChange: (activeOnly: boolean) => void
  onRestore: (pk: string, restoredBy: string) => void
  onViewHistory: (pk: string) => void
  onCloseHistory: () => void
  onUploadCsv: (file: File, actor: string, status: ExclusionStatus) => void
}

export function ExcludedTab({
  items,
  loading,
  statusFilter,
  activeOnly,
  historyTargetPk,
  historyItems,
  bulkResult,
  uploadingCsv,
  restoringPk,
  onStatusFilterChange,
  onActiveOnlyChange,
  onRestore,
  onViewHistory,
  onCloseHistory,
  onUploadCsv,
}: ExcludedTabProps) {
  const [csvFile, setCsvFile] = useState<File | null>(null)
  const [csvActor, setCsvActor] = useState('일괄업로드담당')
  const [csvStatus, setCsvStatus] = useState<ExclusionStatus>('TELECOM_DONE_SYSTEM')
  const [restoreActor, setRestoreActor] = useState('관리자')

  const handleBulkSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!csvFile || !csvActor.trim()) return
    onUploadCsv(csvFile, csvActor.trim(), csvStatus)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <section className="card" aria-label="CSV 일괄 제외 업로드">
        <div className="card-header">
          <h2 className="card-title">
            <Upload size={17} />
            CSV 일괄 제외 업로드
          </h2>
          <span className="top20-meta">
            컬럼 예시: mgm_pmsrgst_pk (또는 bld_nm/plat_plc), reason, evidence
          </span>
        </div>

        <form onSubmit={handleBulkSubmit} className="toolbar-row">
          <div className="field-group">
            <label className="field-label" htmlFor="csv-file-input">
              CSV 파일
            </label>
            <input
              id="csv-file-input"
              type="file"
              accept=".csv,text/csv"
              className="input"
              onChange={(e) => setCsvFile(e.target.files?.[0] ?? null)}
            />
          </div>

          <div className="field-group">
            <label className="field-label" htmlFor="csv-status-select">
              기본 제외 구분
            </label>
            <select
              id="csv-status-select"
              className="select"
              value={csvStatus}
              onChange={(e) => setCsvStatus(e.target.value as ExclusionStatus)}
            >
              {(Object.keys(EXCLUSION_STATUS_LABELS) as ExclusionStatus[]).map((key) => (
                <option key={key} value={key}>
                  {EXCLUSION_STATUS_LABELS[key]}
                </option>
              ))}
            </select>
          </div>

          <div className="field-group">
            <label className="field-label" htmlFor="csv-actor-input">
              처리자
            </label>
            <input
              id="csv-actor-input"
              type="text"
              className="input"
              value={csvActor}
              onChange={(e) => setCsvActor(e.target.value)}
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={!csvFile || !csvActor.trim() || uploadingCsv}
          >
            <Upload size={15} />
            {uploadingCsv ? '업로드 중...' : 'CSV 일괄 업로드'}
          </button>
        </form>

        {bulkResult && (
          <div className="alert alert-info" style={{ marginTop: 12, flexDirection: 'column', alignItems: 'flex-start' }}>
            <div>
              <strong>일괄 처리 결과:</strong> 총 {bulkResult.total_rows}건 중{' '}
              제외 성공 {bulkResult.excluded_count}건 / 미매칭 {bulkResult.not_found_count}건 / 오류{' '}
              {bulkResult.error_count}건
            </div>
            {bulkResult.results.length > 0 && (
              <div className="top20-meta">
                {bulkResult.results.slice(0, 5).map((r) => (
                  <div key={r.row_number}>
                    행 {r.row_number} ({r.identifier}): {r.status}
                    {r.detail ? ` - ${r.detail}` : ''}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </section>

      <section className="card" aria-label="제외 건축물 목록 및 이력">
        <div className="card-header">
          <h2 className="card-title">제외된 건축물 목록</h2>
          <div className="toolbar-row">
            <select
              aria-label="제외 상태 필터"
              className="select"
              value={statusFilter}
              onChange={(e) => onStatusFilterChange(e.target.value as ExclusionStatus | '')}
            >
              <option value="">전체 상태</option>
              {(Object.keys(EXCLUSION_STATUS_LABELS) as ExclusionStatus[]).map((key) => (
                <option key={key} value={key}>
                  {EXCLUSION_STATUS_LABELS[key]}
                </option>
              ))}
            </select>

            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={activeOnly}
                onChange={(e) => onActiveOnlyChange(e.target.checked)}
              />
              현재 제외중만 보기
            </label>

            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span className="field-label">복원자:</span>
              <input
                aria-label="복원 처리자"
                type="text"
                className="input"
                style={{ width: 110 }}
                value={restoreActor}
                onChange={(e) => setRestoreActor(e.target.value)}
              />
            </div>
          </div>
        </div>

        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>인허가 PK</th>
                <th>제외 구분</th>
                <th>처리자 / 일시</th>
                <th>사유</th>
                <th>증빙</th>
                <th>상태</th>
                <th>작업</th>
              </tr>
            </thead>
            <tbody>
              {loading && items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="empty-state">
                    제외 목록을 불러오는 중입니다...
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="empty-state">
                    제외된 건축물이 없습니다.
                  </td>
                </tr>
              ) : (
                items.map((item) => (
                  <tr key={item.id} data-testid={`excluded-row-${item.mgm_pmsrgst_pk}`}>
                    <td style={{ fontWeight: 600 }}>{item.mgm_pmsrgst_pk}</td>
                    <td>{EXCLUSION_STATUS_LABELS[item.status]}</td>
                    <td>
                      <div>{item.actor}</div>
                      <div className="top20-meta">{formatIsoDateTime(item.created_at)}</div>
                    </td>
                    <td>{item.reason || '-'}</td>
                    <td>{item.evidence || '-'}</td>
                    <td>
                      {item.is_active ? (
                        <span className="badge badge-NEAR_COMPLETION">제외중</span>
                      ) : (
                        <span className="badge badge-USE_APPROVED">
                          복원됨 ({item.restored_by ?? '-'})
                        </span>
                      )}
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 6 }}>
                        {item.is_active && (
                          <button
                            type="button"
                            className="btn btn-sm btn-success"
                            disabled={restoringPk === item.mgm_pmsrgst_pk || !restoreActor.trim()}
                            onClick={() =>
                              onRestore(item.mgm_pmsrgst_pk, restoreActor.trim() || '관리자')
                            }
                          >
                            <RotateCcw size={13} />
                            복원
                          </button>
                        )}
                        <button
                          type="button"
                          className="btn btn-sm"
                          onClick={() => onViewHistory(item.mgm_pmsrgst_pk)}
                        >
                          <History size={13} />
                          이력
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {historyTargetPk && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="제외/복원 이력">
          <div className="modal-panel" style={{ maxWidth: 640 }}>
            <div className="modal-header">
              <h3 className="modal-title">제외/복원 이력 ({historyTargetPk})</h3>
              <button type="button" className="btn btn-sm" onClick={onCloseHistory}>
                닫기
              </button>
            </div>
            <div className="table-wrap" style={{ maxHeight: 340, overflowY: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>구분</th>
                    <th>처리자 / 일시</th>
                    <th>사유 / 증빙</th>
                    <th>복원</th>
                  </tr>
                </thead>
                <tbody>
                  {historyItems.map((h) => (
                    <tr key={h.id}>
                      <td>{EXCLUSION_STATUS_LABELS[h.status]}</td>
                      <td>
                        <div>{h.actor}</div>
                        <div className="top20-meta">{formatIsoDateTime(h.created_at)}</div>
                      </td>
                      <td>
                        <div>{h.reason || '-'}</div>
                        <div className="top20-meta">{h.evidence || ''}</div>
                      </td>
                      <td>
                        {h.is_active
                          ? '활성'
                          : `${h.restored_by ?? '-'} (${formatIsoDateTime(h.restored_at)})`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
