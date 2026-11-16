import { Building2, CalendarDays, ListFilter, ShieldOff } from 'lucide-react'

export type ActiveTab = 'targets' | 'monthly' | 'excluded'

interface HeaderProps {
  activeTab: ActiveTab
  onTabChange: (tab: ActiveTab) => void
  excludedCount: number
  apiTrafficToday?: number
  apiDailyLimit?: number
}

export function Header({
  activeTab,
  onTabChange,
  excludedCount,
  apiTrafficToday = 0,
  apiDailyLimit = 10000,
}: HeaderProps) {
  return (
    <header className="app-header">
      <div className="app-header-inner">
        <div className="brand">
          <div className="brand-icon" aria-hidden="true">
            <Building2 size={20} />
          </div>
          <div>
            <h1 className="brand-title">신축 통신공사 사전파악 리포트 시스템</h1>
            <p className="brand-subtitle">건축HUB 인허가 기반 공정 단계별 타겟 발굴 및 제외 관리</p>
          </div>
        </div>

        <div className="header-right">
          <span className="quota-pill" title="일일 건축HUB API 호출량">
            API 트래픽: {apiTrafficToday.toLocaleString('ko-KR')} /{' '}
            {apiDailyLimit.toLocaleString('ko-KR')}
          </span>
          <nav className="nav-tabs" aria-label="주요 화면 탭">
            <button
              type="button"
              className={`nav-tab ${activeTab === 'targets' ? 'active' : ''}`}
              onClick={() => onTabChange('targets')}
            >
              <ListFilter size={16} />
              타겟 건축물 관리
            </button>
            <button
              type="button"
              className={`nav-tab ${activeTab === 'monthly' ? 'active' : ''}`}
              onClick={() => onTabChange('monthly')}
            >
              <CalendarDays size={16} />
              월별 신축 파악
            </button>
            <button
              type="button"
              className={`nav-tab ${activeTab === 'excluded' ? 'active' : ''}`}
              onClick={() => onTabChange('excluded')}
            >
              <ShieldOff size={16} />
              제외 목록 / 일괄 관리
              <span className="tab-badge">{excludedCount}</span>
            </button>
          </nav>
        </div>
      </div>
    </header>
  )
}
