import { Download, FileSpreadsheet, FileText, MapPin, RefreshCw } from 'lucide-react'
import type { RegionItem } from '../types/api'

interface RegionCollectorBarProps {
  sidoList: RegionItem[]
  sigunguList: RegionItem[]
  emdList: RegionItem[]
  selectedSido: string
  selectedSigungu: string
  selectedEmd: string
  useFixture: boolean
  syncing: boolean
  exportingFormat: 'excel' | 'pdf' | null
  onSidoChange: (sidoCd: string) => void
  onSigunguChange: (sigunguCd: string) => void
  onEmdChange: (bjdongCd: string) => void
  onUseFixtureChange: (val: boolean) => void
  onCollect: () => void
  onDownloadReport: (format: 'excel' | 'pdf') => void
}

export function RegionCollectorBar({
  sidoList,
  sigunguList,
  emdList,
  selectedSido,
  selectedSigungu,
  selectedEmd,
  useFixture,
  syncing,
  exportingFormat,
  onSidoChange,
  onSigunguChange,
  onEmdChange,
  onUseFixtureChange,
  onCollect,
  onDownloadReport,
}: RegionCollectorBarProps) {
  return (
    <section className="card" aria-label="지역 선택 및 데이터 수집">
      <div className="card-header">
        <h2 className="card-title">
          <MapPin size={17} />
          지역 선택 및 데이터 수집 / 리포트 다운로드
        </h2>
      </div>

      <div className="toolbar-row">
        <div className="field-group">
          <label className="field-label" htmlFor="region-sido">
            1. 시/도
          </label>
          <select
            id="region-sido"
            className="select"
            value={selectedSido}
            onChange={(e) => onSidoChange(e.target.value)}
          >
            <option value="">시/도 선택</option>
            {sidoList.map((r) => (
              <option key={r.code} value={r.sido_cd}>
                {r.sido_name}
              </option>
            ))}
          </select>
        </div>

        <div className="field-group">
          <label className="field-label" htmlFor="region-sigungu">
            2. 시/군/구
          </label>
          <select
            id="region-sigungu"
            className="select"
            value={selectedSigungu}
            onChange={(e) => onSigunguChange(e.target.value)}
            disabled={!selectedSido}
          >
            <option value="">시/군/구 선택</option>
            {sigunguList.map((r) => (
              <option key={r.code} value={r.sigungu_cd}>
                {r.sigungu_name ?? r.sigungu_cd}
              </option>
            ))}
          </select>
        </div>

        <div className="field-group">
          <label className="field-label" htmlFor="region-emd">
            3. 읍/면/동 (선택)
          </label>
          <select
            id="region-emd"
            className="select"
            value={selectedEmd}
            onChange={(e) => onEmdChange(e.target.value)}
            disabled={!selectedSigungu}
          >
            <option value="00000">전체 (시/군/구 단위)</option>
            {emdList.map((r) => (
              <option key={r.code} value={r.bjdong_cd}>
                {r.emd_name ?? r.bjdong_cd}
              </option>
            ))}
          </select>
        </div>

        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={useFixture}
            onChange={(e) => onUseFixtureChange(e.target.checked)}
          />
          Fixture 데이터 사용
        </label>

        <button
          type="button"
          className="btn btn-primary"
          disabled={!selectedSigungu || syncing}
          onClick={onCollect}
        >
          <RefreshCw size={15} />
          {syncing ? '수집 중...' : '데이터 수집'}
        </button>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn"
            disabled={!selectedSigungu || exportingFormat !== null}
            onClick={() => onDownloadReport('excel')}
          >
            <FileSpreadsheet size={15} />
            <Download size={14} />
            {exportingFormat === 'excel' ? '생성 중...' : 'Excel (.xlsx)'}
          </button>
          <button
            type="button"
            className="btn"
            disabled={!selectedSigungu || exportingFormat !== null}
            onClick={() => onDownloadReport('pdf')}
          >
            <FileText size={15} />
            <Download size={14} />
            {exportingFormat === 'pdf' ? '생성 중...' : 'PDF (.pdf)'}
          </button>
        </div>
      </div>
    </section>
  )
}
