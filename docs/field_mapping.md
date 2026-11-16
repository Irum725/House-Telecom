# 국토교통부 건축HUB 오픈API 필드 매핑 명세서

본 문서는 **신축 통신공사 사전파악 리포트 시스템**의 데이터 수집기(`backend/collector/`)가 사용하는 **국토교통부 건축HUB 건축인허가정보 서비스(`ArchPmsHubService`)** 및 **건축물대장정보 서비스(`BldRgstHubService`)**의 공식 API 엔드포인트, 요청 파라미터, 응답 구조 및 DB(`Building` 테이블) 매핑 규칙을 정의합니다.

---

## 1. 주요 API 엔드포인트

### 1.1 건축인허가정보 서비스 (`ArchPmsHubService`) — 기본 수집 대상
- **Base URL**: `https://apis.data.go.kr/1613000/ArchPmsHubService`
  > 참고: 구 '건축데이터 민간개방시스템'(`1611000/ArchPmsService`)에서 건축HUB 체계(`1613000/ArchPmsHubService`)로 이관됨.
- **오퍼레이션**:
  1. **건축인허가 기본개요 조회**: `/getApBasisOulnInfo` *(핵심 수집 엔드포인트)*
  2. **건축인허가 동별개요 조회**: `/getApDongOulnInfo` *(보조/상세 동 정보 보강용)*

### 1.2 건축물대장정보 서비스 (`BldRgstHubService`) — 선택적 보강(Enrichment)
- **Base URL**: `https://apis.data.go.kr/1613000/BldRgstHubService`
- **오퍼레이션**:
  - **건축물대장 표제부 조회**: `/getBrTitleInfo` *(사용승인 이후 `bld_rgst_pk` (`mgmBldrgstPk`) 매핑 및 준공 후 상세 보강용)*

---

## 2. 요청 파라미터 (Request Parameters)

공통 요청 파라미터 (`GET`):

| 파라미터명 | 필수 여부 | 타입 | 설명 | 예시 |
| :--- | :---: | :--- | :--- | :--- |
| `serviceKey` | 필수 | String | 공공데이터포털 발급 인증키 (Decoding 또는 Encoding 키) | *(환경변수 `DATA_GO_KR_SERVICE_KEY`)* |
| `sigunguCd` | 필수 | String(5) | 행정표준 시군구코드 (5자리) | `41135` (경기도 성남시 분당구) |
| `bjdongCd` | 선택/권장 | String(5) | 행정표준 법정동코드 뒤 5자리 (시군구 전체 조회 시 `00000` 또는 생략) | `10300` (정자동), `00000` |
| `platGbCd` | 선택 | String(1) | 대지구분코드 (`0`: 대지, `1`: 산, `2`: 블록) | `0` |
| `bun` | 선택 | String(4) | 번 (본번, 4자리 0-padding) | `0001` |
| `ji` | 선택 | String(4) | 지 (부번, 4자리 0-padding) | `0000` |
| `startDate` | 선택 | String(8) | 검색 시작일 (`YYYYMMDD`, 허가일 기준) | `20250101` |
| `endDate` | 선택 | String(8) | 검색 종료일 (`YYYYMMDD`, 허가일 기준) | `20261116` |
| `numOfRows` | 선택 | Integer | 한 페이지 결과 수 (기본 10, 최대 100~1000 권장) | `100` |
| `pageNo` | 선택 | Integer | 페이지 번호 (1부터 시작) | `1` |
| `_type` | 권장 | String | 응답 포맷 (`json` 또는 `xml`, 미지정 시 기본 `xml`) | `json` |

---

## 3. 공통 JSON 응답 구조 (Response Envelope)

`_type=json` 요청 시 공공데이터포털 표준 응답 구조:

```json
{
  "response": {
    "header": {
      "resultCode": "00",
      "resultMsg": "NORMAL SERVICE."
    },
    "body": {
      "items": {
        "item": [
          { "...": "..." }
        ]
      },
      "numOfRows": 100,
      "pageNo": 1,
      "totalCount": 25
    }
  }
}
```

### 응답 파싱 주의사항 (Data Quirks)
1. **단건 vs 다건 vs 0건**:
   - `totalCount == 0` 인 경우 `body.items`가 빈 문자열 `""` 또는 `null` 이거나 `item` 키가 없을 수 있음.
   - `totalCount == 1` 인 경우 `body.items.item`이 배열(`[ {...} ]`)이 아닌 **단일 객체(`{...}`)** 로 반환될 수 있으므로 수집기에서 반드시 `list`로 정규화해야 함.
2. **날짜 형식**:
   - `archPmsDay`, `stcnsSchedDay`, `realStcnsDay`, `useAprDay` 등은 `YYYYMMDD` 문자열(예: `"20250315"`)로 오며, 미정/미등록 시 빈 문자열 `""`, 공백 `" "`, 또는 `null` 로 반환됨.
3. **숫자 형식**:
   - `totArea`, `hhldCnt`, `dongCnt` 등이 JSON에서 숫자(`12500.5`, `300`) 또는 문자열(`"12500.5"`, `""`)로 혼재될 수 있어 안전한 형변환이 필요함.
4. **트래픽 제한 및 갱신 주기**:
   - 개발계정 일일 트래픽 제한: **10,000건/일** (`ApiTrafficLog`로 일일 호출 건수 추적).
   - 국토교통부 건축HUB 데이터는 **월간(매월 초) 정기 갱신** 및 수시 반영 특성이 있으므로 증분 수집 및 원본 응답 캐시를 활용함.

---

## 4. 상세 필드 매핑 (`getApBasisOulnInfo` → `Building` 테이블)

| DB 컬럼 (`Building`) | DB 타입 | API 필드명 (`getApBasisOulnInfo`) | 국문 항목명 | 변환/처리 규칙 |
| :--- | :--- | :--- | :--- | :--- |
| `mgm_pmsrgst_pk` *(PK)* | String | `mgmPmsrgstPk` | 관리허가대장PK | 고유 식별자(PK). 공백 strip 후 Upsert 키로 사용 |
| `bld_rgst_pk` | String (nullable) | *(보강: `getBrTitleInfo`의 `mgmBldrgstPk`)* | 관리건축물대장PK | 기본개요에는 없음. 사용승인 완료 건물 보강 시 매핑 |
| `sigungu_cd` | String(5) | `sigunguCd` | 시군구코드 | 5자리 문자열 (예: `"41135"`) |
| `bjdong_cd` | String(5) | `bjdongCd` | 법정동코드 | 5자리 문자열 (예: `"10300"`) |
| `plat_plc` | String | `platPlc` | 대지위치 | 지번 주소 (비어있을 경우 `newPlatPlc` 도로명대지위치 보조 활용 가능) |
| `bld_nm` | String (nullable) | `bldNm` | 건물명 | 공백 strip, 빈 문자열이면 `None` |
| `main_purps_cd_nm` | String (nullable) | `mainPurpsCdNm` | 주용도코드명 | 예: `공동주택`, `업무시설`, `제2종근린생활시설` |
| `tot_area` | Float (nullable) | `totArea` | 연면적 (㎡) | `float` 변환, 빈값/오류 시 `None` |
| `hhld_cnt` | Integer | `hhldCnt` | 세대수 | `int` 변환, 기본값 `0` |
| `dong_cnt` | Integer | `dongCnt` | 동수 | `int` 변환, 기본값 `0` (필요 시 `getApDongOulnInfo` 건수로 보완) |
| `arch_pms_day` | String(8) (nullable) | `archPmsDay` | 건축허가일 | `YYYYMMDD` 정규화, 빈값/유효하지 않으면 `None` |
| `stcns_sched_day` | String(8) (nullable) | `stcnsSchedDay` | 착공예정일 | `YYYYMMDD` 정규화, 빈값이면 `None` |
| `real_stcns_day` | String(8) (nullable) | `realStcnsDay` | 실제착공일 | `YYYYMMDD` 정규화, 빈값이면 `None` |
| `use_apr_day` | String(8) (nullable) | `useAprDay` | 사용승인일 | `YYYYMMDD` 정규화, 빈값이면 `None` |
| `raw_json` | Text / JSON | *(전체 item 객체)* | 원본 JSON | JSON 직렬화 저장 (추후 재평가/디버깅용) |

### 기타 주요 참고 필드 (`getApBasisOulnInfo` 응답에 포함되나 `raw_json`에 보관되는 항목)
- `rnum`: 순번
- `newPlatPlc`: 도로명대지위치
- `platGbCd`: 대지구분코드 (`0`: 대지, `1`: 산, `2`: 블록)
- `bun`, `ji`: 번, 지
- `archGbCd`, `archGbCdNm`: 건축구분코드/명 (예: `신축`, `증축`, `개축`)
- `mainPurpsCd`: 주용도코드
- `platArea`: 대지면적 (㎡)
- `archArea`: 건축면적 (㎡)
- `vlRatEstmTotArea` / `vlRatEstmArea`: 용적률산정연면적 (㎡)
- `bcRat`: 건폐율 (%)
- `vlRat`: 용적률 (%)
- `fmlyCnt`: 가구수
- `hoCnt`: 호수
- `grndFlrCnt`, `ugrndFlrCnt`: 지상층수, 지하층수
- `heit`: 높이 (m)
- `strctCd`, `strctCdNm`: 구조코드/명 (예: `철근콘크리트구조`)
- `pmsnoYear`: 허가번호년
- `pmsnoKndCd`, `pmsnoKndCdNm`: 허가번호종류코드/명
- `crtnDay`: 데이터 생성일자 (`YYYYMMDD`)

---

## 5. 보조 엔드포인트 필드 (`getApDongOulnInfo` & `getBrTitleInfo`)

### 5.1 `getApDongOulnInfo` (건축인허가 동별개요 조회)
- `mgmDongOulnPk`: 관리동별개요PK
- `mgmPmsrgstPk`: 관리허가대장PK (`Building.mgm_pmsrgst_pk`와 조인 키)
- `dongNm`: 동명칭 (예: `101동`)
- `mainAtchGbCd` / `mainAtchGbCdNm`: 주부속구분 (`0`: 주건축물, `1`: 부속건축물)
- `mainPurpsCdNm`: 주용도코드명
- `hhldCnt`, `fmlyCnt`, `hoCnt`: 동별 세대수/가구수/호수
- `totArea`, `archArea`: 동별 연면적/건축면적
- `grndFlrCnt`, `ugrndFlrCnt`: 지상/지하층수
- `rideUseElvtCnt`, `emgenUseElvtCnt`: 승용/비상용 승강기 수

### 5.2 `getBrTitleInfo` (건축물대장 표제부 조회 — 준공 후 보강)
- `mgmBldrgstPk`: 관리건축물대장PK → `Building.bld_rgst_pk`에 매핑
- `sigunguCd`, `bjdongCd`, `platGbCd`, `bun`, `ji`: 지번 매칭 키
- `platPlc`, `newPlatPlc`, `bldNm`: 대지위치, 도로명주소, 건물명
- `mainPurpsCdNm`, `etcPurps`: 주용도코드명, 기타용도
- `totArea`, `hhldCnt`, `fmlyCnt`, `grndFlrCnt`, `ugrndFlrCnt`: 연면적, 세대수 등
- `useAprDay`: 사용승인일
