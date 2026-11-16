import { RotateCcw, Search } from 'lucide-react'
import type { BuildingScale, BuildingStage } from '../types/api'
import {
  BUILDING_SCALE_LABELS,
  BUILDING_STAGE_LABELS,
  BUILDING_STAGE_ORDER,
} from '../types/api'

export interface FilterState {
  stages: BuildingStage[]
  scale: BuildingScale
  mainPurps: string
  minScore: string
  dateFrom: string
  dateTo: string
  q: string
}

interface FilterBarProps {
  filters: FilterState
  onChange: (next: FilterState) => void
  onReset: () => void
}

export function FilterBar({ filters, onChange, onReset }: FilterBarProps) {
  const toggleStage = (stage: BuildingStage) => {
    const exists = filters.stages.includes(stage)
    const nextStages = exists
      ? filters.stages.filter((s) => s !== stage)
      : [...filters.stages, stage]
    onChange({ ...filters, stages: nextStages })
  }

  return (
    <section className="card" aria-label="상세 필터">
      <div className="toolbar-row" style={{ marginBottom: 10 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span className="field-label">공정 단계</span>
          <div className="stage-pills">
            {BUILDING_STAGE_ORDER.map((stage) => {
              const active = filters.stages.includes(stage)
              return (
                <button
                  key={stage}
                  type="button"
                  className={`stage-pill ${active ? 'active' : ''}`}
                  onClick={() => toggleStage(stage)}
                  aria-pressed={active}
                >
                  {BUILDING_STAGE_LABELS[stage]}
                </button>
              )
            })}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginLeft: 'auto' }}>
          <label className="field-label" htmlFor="filter-scale">
            건축물 규모
          </label>
          <select
            id="filter-scale"
            className="select"
            value={filters.scale}
            onChange={(e) => onChange({ ...filters, scale: e.target.value as BuildingScale })}
          >
            {(Object.keys(BUILDING_SCALE_LABELS) as BuildingScale[]).map((key) => (
              <option key={key} value={key}>
                {BUILDING_SCALE_LABELS[key]}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="toolbar-row">
        <div className="field-group" style={{ flex: '1 1 200px' }}>
          <label className="field-label" htmlFor="filter-q">
            건물명 / 대지위치 검색
          </label>
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <Search
              size={14}
              style={{ position: 'absolute', left: 10, color: 'var(--text-muted)' }}
            />
            <input
              id="filter-q"
              type="text"
              className="input"
              style={{ paddingLeft: 30, width: '100%' }}
              placeholder="건물명 또는 주소 입력"
              value={filters.q}
              onChange={(e) => onChange({ ...filters, q: e.target.value })}
            />
          </div>
        </div>

        <div className="field-group">
          <label className="field-label" htmlFor="filter-purps">
            주용도
          </label>
          <input
            id="filter-purps"
            type="text"
            className="input"
            placeholder="예: 공동주택, 근린생활"
            value={filters.mainPurps}
            onChange={(e) => onChange({ ...filters, mainPurps: e.target.value })}
          />
        </div>

        <div className="field-group" style={{ minWidth: 110 }}>
          <label className="field-label" htmlFor="filter-min-score">
            최소 점수
          </label>
          <input
            id="filter-min-score"
            type="number"
            min={0}
            max={100}
            className="input"
            placeholder="0 ~ 100"
            value={filters.minScore}
            onChange={(e) => onChange({ ...filters, minScore: e.target.value })}
          />
        </div>

        <div className="field-group">
          <label className="field-label" htmlFor="filter-date-from">
            허가/착공 시작일
          </label>
          <input
            id="filter-date-from"
            type="date"
            className="input"
            value={filters.dateFrom}
            onChange={(e) => onChange({ ...filters, dateFrom: e.target.value })}
          />
        </div>

        <div className="field-group">
          <label className="field-label" htmlFor="filter-date-to">
            허가/착공 종료일
          </label>
          <input
            id="filter-date-to"
            type="date"
            className="input"
            value={filters.dateTo}
            onChange={(e) => onChange({ ...filters, dateTo: e.target.value })}
          />
        </div>

        <button type="button" className="btn" onClick={onReset}>
          <RotateCcw size={14} />
          초기화
        </button>
      </div>
    </section>
  )
}
