"""API integration tests using FastAPI TestClient."""

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import create_app
from backend.region.service import ensure_regions_seeded
from shared.database import Base, get_db


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Create an isolated TestClient backed by a temporary SQLite DB and report dir."""
    db_path = tmp_path / "test_api.db"
    report_dir = tmp_path / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("REPORT_OUTPUT_DIR", str(report_dir))
    monkeypatch.setenv("DATA_GO_KR_SERVICE_KEY", "")
    monkeypatch.setenv("DISABLE_SCHEDULER", "true")

    test_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    TestingSessionLocal = sessionmaker(
        bind=test_engine, autocommit=False, autoflush=False, expire_on_commit=False
    )

    import shared.models  # noqa: F401

    Base.metadata.create_all(bind=test_engine)
    with TestingSessionLocal() as db:
        ensure_regions_seeded(db)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    test_engine.dispose()


def test_health_and_regions(client: TestClient):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}

    sido_res = client.get("/api/regions/sido")
    assert sido_res.status_code == 200
    sido_codes = {item["sido_cd"] for item in sido_res.json()["items"]}
    assert "41" in sido_codes

    sgg_res = client.get("/api/regions/sigungu", params={"sido_cd": "41"})
    assert sgg_res.status_code == 200
    sgg_codes = {item["sigungu_cd"] for item in sgg_res.json()["items"]}
    assert "41135" in sgg_codes

    emd_res = client.get("/api/regions/emd", params={"sigungu_cd": "41135"})
    assert emd_res.status_code == 200
    assert emd_res.json()["total"] > 0

    params_res = client.get("/api/regions/api-params", params={"code": "4113500000"})
    assert params_res.status_code == 200
    assert params_res.json() == {"sigunguCd": "41135", "bjdongCd": "00000"}

    bad_res = client.get("/api/regions/api-params", params={"code": "abcde"})
    assert bad_res.status_code == 400


def test_full_api_workflow(client: TestClient):
    # 1. Sync fixture data for Bundang (41135)
    sync_res = client.post(
        "/api/buildings/sync",
        json={"sigungu_cd": "41135", "bjdong_cd": "00000", "use_fixture": True},
    )
    assert sync_res.status_code == 200
    sync_data = sync_res.json()
    assert sync_data["fetched_count"] == 12
    assert sync_data["created_count"] == 12

    # 2. List & paginate buildings
    list_res = client.get(
        "/api/buildings",
        params={"sigungu_cd": "41135", "page": 1, "page_size": 5},
    )
    assert list_res.status_code == 200
    page1 = list_res.json()
    assert page1["total"] == 12
    assert len(page1["items"]) == 5
    assert page1["total_pages"] == 3

    # 2b. Scale filter (small vs large)
    small_res = client.get(
        "/api/buildings",
        params={"sigungu_cd": "41135", "scale": "small", "page_size": 50},
    )
    assert small_res.status_code == 200
    small_items = small_res.json()["items"]
    assert len(small_items) >= 4
    small_pks = {item["mgm_pmsrgst_pk"] for item in small_items}
    assert "41135-100234509" in small_pks
    assert "41135-100234512" in small_pks

    large_res = client.get(
        "/api/buildings",
        params={"sigungu_cd": "41135", "scale": "large", "page_size": 50},
    )
    assert large_res.status_code == 200
    large_items = large_res.json()["items"]
    assert len(large_items) >= 1
    large_pks = {item["mgm_pmsrgst_pk"] for item in large_items}
    assert "41135-100234509" not in large_pks

    all_res = client.get(
        "/api/buildings",
        params={"sigungu_cd": "41135", "page": 1, "page_size": 50},
    )
    all_items = all_res.json()["items"]
    assert len(all_items) == 12
    for item in all_items:
        assert "expected_completion_month" in item
        if item["use_apr_day"]:
            assert item["expected_completion_month"] is None
        elif item["real_stcns_day"] or item["stcns_sched_day"]:
            assert item["expected_completion_month"] is not None
            assert len(item["expected_completion_month"]) == 7
    pk1 = all_items[0]["mgm_pmsrgst_pk"]
    pk2 = all_items[1]["mgm_pmsrgst_pk"]
    pk3 = all_items[2]["mgm_pmsrgst_pk"]

    # 3. Building detail & 404
    detail_res = client.get(f"/api/buildings/{pk1}")
    assert detail_res.status_code == 200
    assert detail_res.json()["mgm_pmsrgst_pk"] == pk1
    assert "expected_completion_month" in detail_res.json()
    assert client.get("/api/buildings/NON_EXISTENT_PK").status_code == 404

    # 4. Exclude 2 buildings
    for pk in (pk1, pk2):
        excl_res = client.post(
            "/api/exclusions",
            json={
                "mgm_pmsrgst_pk": pk,
                "actor": "tester",
                "status": "TELECOM_DONE_FIELD",
                "reason": "현장 확인 완료",
            },
        )
        assert excl_res.status_code == 201

    # Excluded buildings omitted by default, present when include_excluded=true
    filtered_res = client.get("/api/buildings", params={"sigungu_cd": "41135"})
    assert filtered_res.json()["total"] == 10
    incl_res = client.get(
        "/api/buildings",
        params={"sigungu_cd": "41135", "include_excluded": True},
    )
    assert incl_res.json()["total"] == 12

    excl_list = client.get("/api/exclusions").json()
    assert excl_list["total"] == 2

    # 5. Restore 1 building -> reappears in search
    restore_res = client.post(
        f"/api/exclusions/{pk1}/restore",
        json={"restored_by": "tester"},
    )
    assert restore_res.status_code == 200
    assert restore_res.json()["is_active"] is False

    after_restore = client.get("/api/buildings", params={"sigungu_cd": "41135"}).json()
    assert after_restore["total"] == 11

    history_res = client.get(f"/api/exclusions/{pk1}/history")
    assert history_res.status_code == 200
    assert history_res.json()["total"] == 1
    assert history_res.json()["items"][0]["restored_by"] == "tester"

    # 6. Bulk CSV exclusion on pk3
    csv_bytes = f"mgm_pmsrgst_pk,reason\n{pk3},일괄제외테스트\n".encode("utf-8")
    bulk_res = client.post(
        "/api/exclusions/bulk-csv",
        files={"file": ("exclude.csv", io.BytesIO(csv_bytes), "text/csv")},
        data={"actor": "csv-admin", "status": "TELECOM_DONE_SYSTEM"},
    )
    assert bulk_res.status_code == 200
    assert bulk_res.json()["excluded_count"] == 1

    # Now 10 active targets (pk2 + pk3 excluded)
    dash_res = client.get("/api/dashboard", params={"sigungu_cd": "41135"})
    assert dash_res.status_code == 200
    dash = dash_res.json()
    assert dash["total_buildings"] == 12
    assert dash["excluded_count"] == 2
    assert dash["active_targets"] == 10

    dash_emd_res = client.get(
        "/api/dashboard", params={"sigungu_cd": "41135", "bjdong_cd": "10300"}
    )
    assert dash_emd_res.status_code == 200
    assert 1 <= dash_emd_res.json()["total_buildings"] < 12

    # 6b. Monthly new building tracking endpoint
    monthly_res = client.get(
        "/api/dashboard/monthly",
        params={"sigungu_cd": "41135", "months": 24, "basis": "all"},
    )
    assert monthly_res.status_code == 200
    monthly = monthly_res.json()
    assert len(monthly["months"]) >= 1
    month_keys = [m["month"] for m in monthly["months"]]
    assert month_keys == sorted(month_keys, reverse=True)
    assert monthly["selected_month"] == month_keys[0]
    assert monthly["total"] == monthly["months"][0]["total_count"]

    target_month = month_keys[-1]
    month_filtered = client.get(
        "/api/dashboard/monthly",
        params={"sigungu_cd": "41135", "month": target_month, "basis": "all"},
    )
    assert month_filtered.status_code == 200
    assert month_filtered.json()["selected_month"] == target_month
    assert month_filtered.json()["total"] == monthly["months"][-1]["total_count"]

    # 7. Generate Excel & PDF reports and download both
    gen_res = client.post(
        "/api/reports/generate",
        json={"sigungu_cd": "41135", "bjdong_cd": "00000", "formats": ["excel", "pdf"]},
    )
    assert gen_res.status_code == 201
    report_run = gen_res.json()
    assert report_run["total_count"] == 10
    report_id = report_run["id"]

    xlsx_dl = client.get(f"/api/reports/{report_id}/download", params={"format": "excel"})
    assert xlsx_dl.status_code == 200
    assert xlsx_dl.content[:2] == b"PK"  # ZIP/XLSX signature

    pdf_dl = client.get(f"/api/reports/{report_id}/download", params={"format": "pdf"})
    assert pdf_dl.status_code == 200
    assert pdf_dl.content[:4] == b"%PDF"

    # 8. Jobs / Interest Regions & Manual Trigger
    ir_res = client.post(
        "/api/jobs/interest-regions",
        json={"sigungu_cd": "41135", "bjdong_cd": "00000", "name": "성남시 분당구"},
    )
    assert ir_res.status_code == 201
    ir_id = ir_res.json()["id"]

    assert client.get("/api/jobs/interest-regions").json()["total"] == 1

    trig_res = client.post("/api/jobs/trigger", json={"interest_region_id": ir_id})
    assert trig_res.status_code == 200
    trig_data = trig_res.json()
    assert trig_data["status"] == "completed"
    assert len(trig_data["report_run_ids"]) == 1

    runs_res = client.get("/api/jobs/runs")
    assert runs_res.status_code == 200
    assert runs_res.json()["total"] >= 2

    del_res = client.delete(f"/api/jobs/interest-regions/{ir_id}")
    assert del_res.status_code == 204
    assert client.get("/api/jobs/interest-regions").json()["total"] == 0

    # 9. Reset collected buildings & exclusion history
    reset_res = client.delete("/api/buildings/reset")
    assert reset_res.status_code == 200
    assert reset_res.json()["deleted_buildings"] == 12
    assert client.get("/api/buildings").json()["total"] == 0
