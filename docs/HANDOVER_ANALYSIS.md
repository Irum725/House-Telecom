# House-Telecom 프로젝트 현황, 원인 분석 및 인수인계 문서

> 최종 업데이트: 2026-11-16  
> 저장소: https://github.com/Irum725/House-Telecom

---

## 1. 시스템 구성 요약

- **공통 계약 (`shared/`)**:
  - `shared/enums.py`: `BuildingStage` (`PERMITTED`, `START_SCHEDULED`, `UNDER_CONSTRUCTION`, `NEAR_COMPLETION`, `USE_APPROVED`), `ExclusionStatus` (`TELECOM_DONE_FIELD`, `TELECOM_DONE_SYSTEM`, `NOT_TARGET`, `ON_HOLD`)
  - `shared/database.py`: `PROJECT_ROOT` 기준 절대 경로 SQLite(`house_telecom.db`) 또는 `DATABASE_URL` 환경변수 지원
  - `shared/models.py`: `Region`, `Building`, `ExclusionHistory`, `InterestRegion`, `ReportRun`, `ApiTrafficLog`
  - `shared/schemas.py`, `shared/openapi.yaml`: REST API 요청/응답 스키마 (`expected_completion_month`, `scale`, `MonthlySummaryResponse` 포함)
- **백엔드 (`backend/`)**:
  - `backend/region/`: 법정동코드 적재(`seed_data.py`, `parser.py`, `service.py`), 2026-07-01 인천광역시 개편(제물포구·영종구·서해구·검단구, 구 중구·동구 비활성화) 반영
  - `backend/collector/`: 국토교통부 건축HUB(`ArchPmsHubService/getApBasisOulnInfo`) 연동, 페이지네이션, 지수 백오프 재시도, 일일 트래픽 제한(10,000건), 월별 캐시(`data/raw_cache/`), Fixture 시뮬레이션
  - `backend/stage/`: `rules.yaml` 기반 공정 단계 분류, 우선순위 점수(0~100), 연면적 기반 `estimate_completion_month` (`YYYY-MM`)
  - `backend/exclusion/`: 제외/복원/이력/CSV 일괄 제외 및 공통 필터 `apply_exclusion_filter`
  - `backend/report/`: `openpyxl` Excel(`요약`, `미확인 대상`, `준공임박`, `제외 목록`) 및 `WeasyPrint`(Linux/GTK) / `PyMuPDF` 폴백(Windows) PDF 생성
  - `backend/jobs/`: `APScheduler` 주간 배치 및 직전 대비 신규/단계변경 diff
  - `backend/app/`, `backend/routers/`: FastAPI 서버 (`main.py`, `wsgi.py` PythonAnywhere 동기식 WSGI 어댑터)
- **프론트엔드 (`frontend/`)**:
  - React + Vite + TypeScript (개발 포트 `4002`, 백엔드 프록시 `127.0.0.1:8001`, 빌드 산출물 `frontend/dist/` 포함)

---

## 2. 발생했던 주요 문제와 근본 원인 분석 (Root Cause Analysis)

### 문제 A. 인증키 입력 후에도 옛 성남(판교/정자/수내) 주소 데이터가 보였던 현상
1. **초기 DB 잔존 Fixture 데이터**:
   - 이전에 `Fixture 데이터 사용` 모드로 인천(`28150`, `28160`, `28260`)을 수집하면서 생성된 가상 합성 데이터 36건(`[제물포구] 판교 더샵 포레스트` 등, `mgm_pmsrgst_pk`가 `*-1002345*`)이 로컬 `house_telecom.db`에 남아 있었음.
   - 초기 화면(지역 미선택 상태)에서 `GET /api/buildings`가 DB 전체를 `priority_score` 내림차순으로 조회하므로, 95점짜리 옛 가상 데이터가 최상단에 계속 노출됨.
   - **조치**: 로컬 `house_telecom.db`에서 해당 가상 데이터 36건 삭제 완료.
2. **`.env` 미로드 및 프론트엔드 `useFixture` 기본값**:
   - `uvicorn backend.app.main:app` 실행 시 `load_dotenv()`가 호출되지 않아 `DATA_GO_KR_SERVICE_KEY`를 읽지 못했음.
   - `frontend/src/App.tsx`의 `useFixture` 초기값이 무조건 `true`여서 실 API 키가 있어도 Fixture 모드로 요청됨.
   - **조치**: `backend/app/main.py` 시작 시 `.env` 자동 로드(`load_dotenv`), `GET /api/config` (`live_api_configured`) 추가, `App.tsx`에서 실 API 키가 감지되면 자동으로 `useFixture = false` 전환.

### 문제 B. 실 API 수집 시 일부 지역(예: 강원 원주시 `51130`) 500 오류 및 데이터 누락
1. **`bjdongCd=00000` 파라미터 생략 시 국토교통부 API 오류**:
   - `backend/collector/client.py`에서 `bjdong_cd == "00000"`일 때 `bjdongCd` 파라미터를 생략하고 요청했으나, 국토교통부 `getApBasisOulnInfo`는 `bjdongCd` 누락 시 `OpenAPI_ServiceResponse` 에러를 반환함.
   - 또한 `bjdongCd=00000`은 "시군구 전체" 와일드카드가 아니라 동 코드가 `00000`인 일부 미분류 건만 반환함.
   - **조치**:
     - `client.py`에서 항상 `bjdongCd`를 명시 전달하도록 수정.
     - `bjdong_cd == "00000"`으로 실 API 호출 시 DB `Region` 테이블에 등록된 해당 시군구의 활성 하위 법정동(`bjdong_cd != "00000"`) 목록을 자동 순회(`_resolve_target_bjdongs`)하도록 개선.
2. **`OpenAPI_ServiceResponse` 오류 파싱 누락**:
   - `apis.data.go.kr`이 간헐적 503/오류 시 `{"response": ...}` 대신 `{"OpenAPI_ServiceResponse": {"cmmMsgHeader": ...}}`를 반환할 때 `normalize_items`가 원인 코드를 추출하지 못하고 `CollectorError`를 발생시켰음.
   - **조치**: `backend/collector/parser.py`에서 `OpenAPI_ServiceResponse`를 감지해 `ApiResponseError`로 명확히 변환.
3. **과거 연도(2000~2022년) 및 비신축(대수선/철거 등) 혼입**:
   - 국토교통부 `getApBasisOulnInfo`는 날짜 최신순이 아니라 지번순으로 2000년 이후 전체 이력을 반환함.
   - **조치**: `client.py`의 `_is_recent_new_construction`으로 실 API 수집 시 2023-01-01 이후 및 `신축` 건만 적재하도록 필터링.

### 문제 C. PythonAnywhere 배포 시 `502-backend` 타임아웃 및 `Internal server error`
1. **uWSGI 스레드 차단으로 인한 `a2wsgi` 데드락**:
   - PythonAnywhere 기본 uWSGI 워커는 `--enable-threads`가 꺼져 있어 백그라운드 스레드를 사용하는 `a2wsgi` 변환 계층이 응답 대기 상태에서 타임아웃(`502-backend`) 발생.
   - **조치**: `FastAPI` `TestClient`를 이용해 동일 스레드에서 동기 처리하는 `backend/app/wsgi.py` 구현.
2. **WSGI 모드에서 ASGI `lifespan` 미실행**:
   - WSGI는 FastAPI `lifespan`을 호출하지 않으므로 `init_db()` 및 `ensure_regions_seeded()`가 실행되지 않아 `no such table: regions` 500 오류 발생.
   - **조치**: `create_app()` 내부에서 `init_db()`와 `ensure_regions_seeded()`를 직접 호출하도록 수정.

---

## 3. 주의 및 향후 확인 필요 사항 (Open Risks)

1. **읍/면/동 시드 커버리지 (`backend/region/seed_data.py`)**:
   - 내장 시드(`SEED_LEGAL_DONG_ROWS`)는 전국 주요 시·군·구 및 핵심 읍/면/동(분당구 18개 동, 인천 개편 구, 강원 춘천·원주·강릉 주요 동 등)을 포함합니다.
   - 전국 모든 읍/면/동 및 2026-07-01 인천 신설 구(`제물포구`, `영종구`, `검단구`)의 공식 10자리 법정동코드 전체를 사용하려면 행정표준코드관리시스템(`code.go.kr`)에서 받은 법정동코드 TXT/CSV를 `backend.region.service.load_regions_from_file()`로 적재해야 합니다.
2. **실 API 일일 트래픽 및 페이지네이션 한도**:
   - 개발계정 일일 트래픽 한도는 10,000건입니다. 하위 법정동이 많은 시/군/구를 `전체(00000)`로 한 번에 수집하면 여러 동×여러 페이지를 호출하므로, 실무에서는 관심 읍/면/동을 지정하거나 `max_pages`로 호출량을 제어하는 것을 권장합니다.
3. **검증 상태**:
   - `py -m pytest -v`: 89 passed, 0 failed
   - `cd frontend && npm.cmd run test`: 6 passed
   - `cd frontend && npm.cmd run build`: 성공 (`frontend/dist/` 최신화 완료)
