import { useState } from 'react'
import { X } from 'lucide-react'
import type { BuildingSummary, ExclusionStatus } from '../types/api'
import { EXCLUSION_STATUS_LABELS } from '../types/api'

interface ExclusionModalProps {
  building: BuildingSummary
  initialStatus: ExclusionStatus
  submitting: boolean
  onClose: () => void
  onSubmit: (payload: {
    mgm_pmsrgst_pk: string
    status: ExclusionStatus
    actor: string
    reason: string
    evidence: string
  }) => void
}

export function ExclusionModal({
  building,
  initialStatus,
  submitting,
  onClose,
  onSubmit,
}: ExclusionModalProps) {
  const [status, setStatus] = useState<ExclusionStatus>(initialStatus)
  const [actor, setActor] = useState('현장영업담당')
  const [reason, setReason] = useState('')
  const [evidence, setEvidence] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!actor.trim()) return
    onSubmit({
      mgm_pmsrgst_pk: building.mgm_pmsrgst_pk,
      status,
      actor: actor.trim(),
      reason: reason.trim(),
      evidence: evidence.trim(),
    })
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="excl-modal-title">
      <div className="modal-panel">
        <div className="modal-header">
          <h3 id="excl-modal-title" className="modal-title">
            제외 사유 및 증빙 등록
          </h3>
          <button type="button" className="btn btn-sm" onClick={onClose} aria-label="닫기">
            <X size={15} />
          </button>
        </div>

        <div style={{ fontSize: '0.86rem', background: 'var(--surface-alt)', padding: 10, borderRadius: 8 }}>
          <div style={{ fontWeight: 700 }}>{building.bld_nm || '(건물명 미상)'}</div>
          <div className="top20-meta">
            {building.plat_plc ?? '-'} · PK: {building.mgm_pmsrgst_pk}
          </div>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div className="field-group">
            <label className="field-label" htmlFor="excl-status">
              제외 구분
            </label>
            <select
              id="excl-status"
              className="select"
              value={status}
              onChange={(e) => setStatus(e.target.value as ExclusionStatus)}
            >
              {(Object.keys(EXCLUSION_STATUS_LABELS) as ExclusionStatus[]).map((key) => (
                <option key={key} value={key}>
                  {EXCLUSION_STATUS_LABELS[key]}
                </option>
              ))}
            </select>
          </div>

          <div className="field-group">
            <label className="field-label" htmlFor="excl-actor">
              처리자 *
            </label>
            <input
              id="excl-actor"
              type="text"
              className="input"
              required
              value={actor}
              onChange={(e) => setActor(e.target.value)}
            />
          </div>

          <div className="field-group">
            <label className="field-label" htmlFor="excl-reason">
              사유
            </label>
            <textarea
              id="excl-reason"
              className="textarea"
              rows={3}
              placeholder="현장 확인 내용 또는 제외 사유를 입력하세요"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>

          <div className="field-group">
            <label className="field-label" htmlFor="excl-evidence">
              증빙 메모 / 사진 경로
            </label>
            <input
              id="excl-evidence"
              type="text"
              className="input"
              placeholder="예: /photos/bundang_site_01.jpg 또는 개통번호"
              value={evidence}
              onChange={(e) => setEvidence(e.target.value)}
            />
          </div>

          <div className="modal-footer">
            <button type="button" className="btn" onClick={onClose} disabled={submitting}>
              취소
            </button>
            <button type="submit" className="btn btn-primary" disabled={submitting || !actor.trim()}>
              {submitting ? '저장 중...' : '제외 확정'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
