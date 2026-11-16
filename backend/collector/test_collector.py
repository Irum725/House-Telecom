"""Unit tests for backend/collector using recorded JSON fixtures and MockTransport."""

import json
from datetime import date
from pathlib import Path

import httpx
import pytest
from sqlalchemy.orm import Session, sessionmaker

from backend.collector import (
    ApiResponseError,
    ArchHubCollector,
    DailyQuotaExceededError,
    RawResponseCache,
    TrafficLimiter,
    normalize_items,
    parse_ap_basis_item,
    sync_buildings,
)
from shared.database import Base, create_db_engine
from shared.enums import BuildingStage
from shared.models import ApiTrafficLog, Building
from shared.schemas import BuildingSyncRequest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture()
def db_session() -> Session:
    engine = create_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _load_fixture(name: str) -> dict:
    with (FIXTURES_DIR / name).open("r", encoding="utf-8") as f:
        return json.load(f)


def test_fixture_sync_bundang_all_stages(db_session: Session) -> None:
    req = BuildingSyncRequest(sigungu_cd="41135", bjdong_cd="00000", use_fixture=True)
    res = sync_buildings(db_session, req)

    assert res.fetched_count == 12
    assert res.created_count == 12
    assert res.updated_count == 0
    assert res.api_calls_used == 0

    buildings = db_session.query(Building).all()
    assert len(buildings) == 12

    stages = {b.stage for b in buildings}
    assert stages == {
        BuildingStage.PERMITTED,
        BuildingStage.START_SCHEDULED,
        BuildingStage.UNDER_CONSTRUCTION,
        BuildingStage.NEAR_COMPLETION,
        BuildingStage.USE_APPROVED,
    }

    by_pk = {b.mgm_pmsrgst_pk: b for b in buildings}
    assert by_pk["41135-100234509"].main_purps_cd_nm == "단독주택"
    assert by_pk["41135-100234509"].tot_area == 198.5
    assert by_pk["41135-100234509"].hhld_cnt == 1
    assert by_pk["41135-100234509"].stage == BuildingStage.PERMITTED

    assert by_pk["41135-100234510"].main_purps_cd_nm == "다가구주택"
    assert by_pk["41135-100234510"].tot_area == 420.0
    assert by_pk["41135-100234510"].hhld_cnt == 8
    assert by_pk["41135-100234510"].stage == BuildingStage.START_SCHEDULED

    assert by_pk["41135-100234511"].main_purps_cd_nm == "다세대주택"
    assert by_pk["41135-100234511"].tot_area == 615.0
    assert by_pk["41135-100234511"].hhld_cnt == 12
    assert by_pk["41135-100234511"].stage == BuildingStage.UNDER_CONSTRUCTION

    assert by_pk["41135-100234512"].main_purps_cd_nm == "제1종근린생활시설"
    assert by_pk["41135-100234512"].tot_area == 285.0
    assert by_pk["41135-100234512"].hhld_cnt == 0
    assert by_pk["41135-100234512"].stage == BuildingStage.NEAR_COMPLETION


def test_fixture_sync_filtered_by_bjdong(db_session: Session) -> None:
    req = BuildingSyncRequest(sigungu_cd="41135", bjdong_cd="10300", use_fixture=True)
    res = sync_buildings(db_session, req)

    assert res.fetched_count == 2
    assert res.created_count == 2
    pks = {b.mgm_pmsrgst_pk for b in db_session.query(Building).all()}
    assert pks == {"41135-100234501", "41135-100234507"}


def test_incremental_upsert_skips_unchanged_and_updates_changed(
    db_session: Session, tmp_path: Path
) -> None:
    req = BuildingSyncRequest(sigungu_cd="41135", bjdong_cd="00000", use_fixture=True)
    first = sync_buildings(db_session, req)
    assert first.created_count == 12

    second = sync_buildings(db_session, req)
    assert second.created_count == 0
    assert second.updated_count == 0

    # Now simulate an updated item via MockTransport
    updated_payload = _load_fixture("single_item_edge.json")
    updated_payload["response"]["body"]["items"]["item"]["mgmPmsrgstPk"] = "41135-100234505"
    updated_payload["response"]["body"]["items"]["item"]["useAprDay"] = "20261110"

    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=updated_payload))
    client = httpx.Client(transport=transport)
    collector = ArchHubCollector(
        db=db_session,
        service_key="test-key",
        http_client=client,
        cache=RawResponseCache(cache_dir=tmp_path / "cache"),
    )
    res = collector.sync(
        BuildingSyncRequest(sigungu_cd="41135", bjdong_cd="00000", num_of_rows=100, use_fixture=False),
        use_cache=False,
    )
    assert res.created_count == 0
    assert res.updated_count == 1
    b = db_session.get(Building, "41135-100234505")
    assert b is not None
    assert b.use_apr_day == "20261110"
    assert b.stage == BuildingStage.USE_APPROVED


def test_normalize_items_edge_cases() -> None:
    single = _load_fixture("single_item_edge.json")
    items, total = normalize_items(single)
    assert total == 1
    assert len(items) == 1
    parsed = parse_ap_basis_item(items[0])
    assert parsed["mgm_pmsrgst_pk"] == "41135-100299999"
    assert parsed["tot_area"] == 320.5
    assert parsed["hhld_cnt"] == 1
    assert parsed["stcns_sched_day"] is None
    assert parsed["real_stcns_day"] is None

    empty = _load_fixture("empty_response.json")
    items_empty, total_empty = normalize_items(empty)
    assert total_empty == 0
    assert items_empty == []

    err_payload = {"response": {"header": {"resultCode": "22", "resultMsg": "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR"}}}
    with pytest.raises(ApiResponseError):
        normalize_items(err_payload)


def test_live_pagination_retry_and_cache(db_session: Session, tmp_path: Path) -> None:
    page1 = _load_fixture("bundang_41135_page1.json")
    page2 = _load_fixture("bundang_41135_page2.json")
    attempts = {"page1": 0, "page2": 0}
    sleep_delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page_no = request.url.params.get("pageNo")
        if page_no == "1":
            attempts["page1"] += 1
            if attempts["page1"] == 1:
                return httpx.Response(503, text="Service Unavailable")
            return httpx.Response(200, json=page1)
        attempts["page2"] += 1
        return httpx.Response(200, json=page2)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    cache = RawResponseCache(cache_dir=tmp_path / "cache")
    collector = ArchHubCollector(
        db=db_session,
        service_key="test-key",
        http_client=client,
        cache=cache,
        max_retries=2,
        base_backoff_seconds=0.25,
        sleep_fn=sleep_delays.append,
    )

    req = BuildingSyncRequest(sigungu_cd="41135", bjdong_cd="00000", num_of_rows=7, use_fixture=False)
    res = collector.sync(req, use_cache=True)

    assert res.fetched_count == 12
    assert res.created_count == 12
    assert res.api_calls_used == 3  # 1 failed + 1 retry for page1, 1 for page2
    assert res.remaining_daily_quota == 9997
    assert sleep_delays == [0.25]

    # Second run within the same month hits cache -> 0 API calls
    res_cached = collector.sync(req, use_cache=True)
    assert res_cached.fetched_count == 12
    assert res_cached.api_calls_used == 0
    assert res_cached.remaining_daily_quota == 9997


def test_monthly_cache_partitioning(tmp_path: Path) -> None:
    cache = RawResponseCache(cache_dir=tmp_path / "cache")
    payload = _load_fixture("empty_response.json")
    cache.set("getApBasisOulnInfo", "41135", "00000", 1, 100, payload, month_bucket="2026-10")

    assert cache.get("getApBasisOulnInfo", "41135", "00000", 1, 100, month_bucket="2026-10") is not None
    assert cache.get("getApBasisOulnInfo", "41135", "00000", 1, 100, month_bucket="2026-11") is None


def test_daily_quota_limit_enforced(db_session: Session) -> None:
    limiter = TrafficLimiter(db_session, daily_limit=2)
    today = date(2026, 11, 16)
    assert limiter.consume(1, target_date=today) == 1
    assert limiter.consume(1, target_date=today) == 0

    with pytest.raises(DailyQuotaExceededError):
        limiter.consume(1, target_date=today)

    log = db_session.query(ApiTrafficLog).filter_by(log_date=today).one()
    assert log.request_count == 2
