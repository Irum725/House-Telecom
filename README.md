# House-Telecom (신축·인허가 건축물 통신영업 타겟 플랫폼)

국토교통부 건축HUB(건축인허가정보) 데이터를 기반으로 신축/인허가 건축물을 수집하고, 공정 단계(`PERMITTED` → `START_SCHEDULED` → `UNDER_CONSTRUCTION` → `NEAR_COMPLETION` → `USE_APPROVED`)와 통신영업 우선순위를 자동 산출하며, 기개통/비대상 건을 제외 관리하고 Excel/PDF 리포트를 자동 생성하는 플랫폼입니다.

## 아키텍처 (Architecture)

- `shared/`: 공통 Enum (`BuildingStage`, `ExclusionStatus`), SQLAlchemy 2.0 ORM 모델, Pydantic v2 스키마, OpenAPI 계약 (`shared/openapi.yaml`)
- `backend/region/`: 법정동코드(행정표준코드) 로더 및 시/도 → 시/군/구 → 읍/면/동 계층 조회
- `backend/collector/`: 건축HUB API 연동 클라이언트, 일일 트래픽 제한 관리(`ApiTrafficLog`), 적재/업서트 ([필드 매핑 문서](docs/field_mapping.md))
- `backend/stage/`: 공정 단계 분류 엔진 및 통신영업 우선순위 점수 계산 (`backend/stage/rules.yaml`)
- `backend/exclusion/`: 제외(현장개통/자사시스템/비대상/보류) 및 복원 이력 관리, CSV 일괄 제외
- `backend/report/`: Excel (`openpyxl`) / PDF (`WeasyPrint` 및 Windows `PyMuPDF` 폴백) 리포트 생성
- `backend/jobs/`: APScheduler 기반 주간 리포트 파이프라인, 직전 대비 변동(diff) 산출 및 CLI
- `backend/app/`, `backend/routers/`: FastAPI REST API 서버 (`backend/app/main.py`)
- `frontend/`: React + Vite + TypeScript 대시보드 UI

## 서비스키 발급 방법 (공공데이터포털 data.go.kr)

1. [공공데이터포털(data.go.kr)](https://www.data.go.kr)에 로그인합니다.
2. 검색창에 **`국토교통부_건축HUB_건축인허가정보`**를 검색하여 상세 페이지로 이동합니다.
3. **활용신청** 버튼을 클릭하고, 활용 목적을 입력하여 승인을 받습니다(일반적으로 자동 승인).
4. **마이페이지 → 데이터 활용 → 오픈API → 개발계정**에서 발급된 **일반 인증키(Decoding 또는 Encoding)**를 확인합니다.
   - `httpx` 요청 파라미터로 전달 시 이중 인코딩을 방지하려면 **Decoding 키**를 `.env`의 `DATA_GO_KR_SERVICE_KEY`에 입력하는 것을 권장합니다. (서비스키가 없거나 기본 플레이스홀더인 경우 로컬 fixture 모드로 동작합니다.)
5. 개발계정 일일 트래픽 제한은 기본 `10,000`건이며, 플랫폼 내 `ApiTrafficLog`에서 일별 호출량을 추적합니다.

## `.env` 예시

```bash
cp .env.example .env
```

```dotenv
# 국토교통부 건축HUB 공공데이터포털 인증키 (Decoding/Encoding 키 확인)
DATA_GO_KR_SERVICE_KEY=your_data_go_kr_service_key_here

# Database (SQLite dev default; PostgreSQL e.g. postgresql+psycopg://user:pass@localhost:5432/house_telecom)
DATABASE_URL=sqlite:///./house_telecom.db

# Output directories
REPORT_OUTPUT_DIR=./data/reports
UPLOAD_EVIDENCE_DIR=./data/evidence

# API Traffic daily limit (dev account default: 10000)
DATA_GO_KR_DAILY_LIMIT=10000

# Scheduler timezone
SCHEDULER_TIMEZONE=Asia/Seoul
```

## 실행 방법

### 원클릭 실행 (권장)

- **Windows**: 탐색기에서 `start.bat`를 더블 클릭하거나 터미널에서 실행합니다.
  ```cmd
  start.bat
  ```
- **macOS**: Finder에서 `start.command`를 더블 클릭하거나 터미널에서 `start.sh`를 실행합니다. (최초 실행 시 `chmod +x start.sh start.command` 필요할 수 있음)
  ```bash
  chmod +x start.sh start.command
  ./start.sh
  ```
  - 두 런처 모두 `.venv` 생성/의존성 설치, `.env` 자동 생성, `frontend/node_modules` 설치 후 Backend(`127.0.0.1:8001`)와 Frontend(`http://localhost:4002`)를 실행하고 브라우저를 자동으로 엽니다.

### 수동 실행

#### 1. 설치

```bash
pip install -e ".[dev]"
cd frontend && npm.cmd install
```

### 2. Backend (FastAPI)

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8001
```

### 3. Frontend (Vite + React)

```bash
cd frontend && npm.cmd run dev
```

### 4. Scheduler CLI (수동 리포트 파이프라인 실행)

```bash
# 로컬 fixture 데이터로 경기도 성남시 분당구(41135) 즉시 실행
python -m backend.jobs --region 41135 --fixture
```

### 5. 테스트 및 빌드

```bash
# Backend 전체 테스트
py -m pytest

# Frontend 테스트 및 프로덕션 빌드 (Windows PowerShell에서는 npm.cmd 사용)
cd frontend && npm.cmd run test && npm.cmd run build
```

## 주요 기능

- **공정 단계 자동 분류 & 우선순위 산정**: `PERMITTED` → `START_SCHEDULED` → `UNDER_CONSTRUCTION` → `NEAR_COMPLETION` → `USE_APPROVED`
- **월 단위 신축 건물 파악 (`GET /api/dashboard/monthly`)**: 최근 12개월 월별 허가/착공예정/착공진행/사용승인 건수, 세대수, 연면적 추이 차트 및 특정 월(`YYYY-MM`) 클릭 시 해당 월 건물 목록 드릴다운
- **제외 및 복원 이력 관리**: 현장 개통완료, 자사 시스템 개통완료, 영업 비대상, 보류 및 CSV 일괄 제외/복원
- **Excel / PDF 리포트 자동 생성**: `요약`, `미확인 대상`, `준공임박`, `제외 목록` 시트 및 주간 변동(diff) 추적

## 참고 문서

- [건축HUB 인허가정보 API 필드 매핑 문서 (docs/field_mapping.md)](docs/field_mapping.md)
- [REST API OpenAPI 스펙 (shared/openapi.yaml)](shared/openapi.yaml)
