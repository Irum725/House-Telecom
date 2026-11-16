"""Unit and integration tests for backend/jobs/."""

from __future__ import annotations

from pathlib import Path

import openpyxl
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.exclusion import exclude_building
from backend.jobs import (
    JOB_ID_PREFIX,
    create_scheduler,
    list_scheduled_jobs,
    parse_region_code,
    run_all_active_regions,
    run_weekly_pipeline,
    sync_interest_region_jobs,
)
from shared.database import Base
from shared.enums import BuildingStage, ExclusionStatus
from shared.models import Building, InterestRegion, Region, ReportRun


@pytest.fixture()
def db_session_factory(tmp_path: Path) -> sessionmaker[Session]:
    db_path = tmp_path / "test_jobs.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture()
def db_session(db_session_factory: sessionmaker[Session]) -> Session:
    session = db_session_factory()
    # Seed 분당구 region metadata for report header
    session.add(
        Region(
            code="4113500000",
            sido_cd="41",
            sigungu_cd="41135",
            bjdong_cd="00000",
            sido_name="경기도",
            sigungu_name="성남시 분당구",
            emd_name=None,
            is_active=True,
        )
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()


def test_parse_region_code() -> None:
    assert parse_region_code("41135") == ("41135", "00000")
    assert parse_region_code("4113510300") == ("41135", "10300")
    with pytest.raises(ValueError):
        parse_region_code("123")
    with pytest.raises(ValueError):
        parse_region_code("4113A")


def test_run_weekly_pipeline_creates_reports_and_detects_diff(
    db_session: Session, tmp_path: Path
) -> None:
    # 1st run with fixture data for 성남시 분당구 (41135)
    run1 = run_weekly_pipeline(
        "41135",
        db=db_session,
        use_fixture=True,
        output_dir=tmp_path,
    )

    assert run1.id is not None
    assert run1.region_code == "4113500000"
    assert run1.total_count == 12
    assert run1.new_count == 12
    assert run1.stage_changed_count == 0
    assert run1.excel_path is not None
    assert run1.pdf_path is not None

    excel_file = Path(run1.excel_path)
    pdf_file = Path(run1.pdf_path)
    assert excel_file.exists() and excel_file.stat().st_size > 0
    assert pdf_file.exists() and pdf_file.stat().st_size > 0
    assert pdf_file.read_bytes().startswith(b"%PDF")

    wb = openpyxl.load_workbook(excel_file)
    assert "미확인 대상" in wb.sheetnames
    target_ws = wb["미확인 대상"]
    # Header row + 8 data rows
    assert target_ws.max_row - 1 == run1.total_count
    wb.close()

    # Mutate DB: add 1 new building and advance 1 existing building to USE_APPROVED
    existing_buildings = db_session.query(Building).order_by(Building.mgm_pmsrgst_pk.asc()).all()
    target_to_change = next(b for b in existing_buildings if b.stage != BuildingStage.USE_APPROVED)
    old_stage = target_to_change.stage.value
    target_to_change.use_apr_day = "20260115"

    new_building = Building(
        mgm_pmsrgst_pk="41135-NEW-TEST-001",
        sigungu_cd="41135",
        bjdong_cd="10300",
        plat_plc="경기도 성남시 분당구 정자동 999",
        bld_nm="테스트 신규 오피스텔",
        main_purps_cd_nm="업무시설",
        tot_area=3500.0,
        hhld_cnt=50,
        dong_cnt=1,
        arch_pms_day="20260101",
        stage=BuildingStage.PERMITTED,
        priority_score=0.0,
    )
    db_session.add(new_building)
    db_session.commit()

    # 2nd run: skip_collect=True so our DB mutations are preserved and evaluated
    run2 = run_weekly_pipeline(
        "41135",
        db=db_session,
        skip_collect=True,
        output_dir=tmp_path,
    )

    assert run2.id != run1.id
    assert run2.total_count == 13
    assert run2.new_count == 1
    assert run2.stage_changed_count == 1
    assert Path(run2.excel_path).exists()
    assert Path(run2.pdf_path).exists()

    assert run2.diff_json is not None
    new_pks = [item["mgm_pmsrgst_pk"] for item in run2.diff_json["new_buildings"]]
    assert new_pks == ["41135-NEW-TEST-001"]

    changed = run2.diff_json["stage_changed_buildings"]
    assert len(changed) == 1
    assert changed[0]["mgm_pmsrgst_pk"] == target_to_change.mgm_pmsrgst_pk
    assert changed[0]["old_stage"] == old_stage
    assert changed[0]["new_stage"] == BuildingStage.USE_APPROVED.value

    # 3rd run: exclude 1 building and verify total_count drops
    exclude_building(
        db_session,
        mgm_pmsrgst_pk="41135-NEW-TEST-001",
        actor="tester",
        status=ExclusionStatus.TELECOM_DONE_FIELD,
        reason="현장 개통 확인",
    )
    run3 = run_weekly_pipeline(
        "41135",
        db=db_session,
        skip_collect=True,
        output_dir=tmp_path,
    )
    assert run3.total_count == 12


def test_run_all_active_regions_and_scheduler_sync(
    db_session: Session,
    db_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    active = InterestRegion(
        sigungu_cd="41135",
        bjdong_cd="00000",
        name="경기도 성남시 분당구",
        is_active=True,
        cron_expr="0 6 * * 1",
    )
    inactive = InterestRegion(
        sigungu_cd="11680",
        bjdong_cd="00000",
        name="서울특별시 강남구",
        is_active=False,
        cron_expr="0 6 * * 1",
    )
    db_session.add_all([active, inactive])
    db_session.commit()

    runs = run_all_active_regions(
        db=db_session,
        use_fixture=True,
        output_dir=tmp_path,
    )
    assert len(runs) == 1
    assert runs[0].region_code == "4113500000"
    assert db_session.query(ReportRun).count() == 1

    scheduler = create_scheduler(
        session_factory=db_session_factory,
        sync_from_db=True,
        use_fixture=True,
        output_dir=tmp_path,
    )
    jobs = list_scheduled_jobs(scheduler)
    assert len(jobs) == 1
    assert jobs[0]["id"] == f"{JOB_ID_PREFIX}{active.id}"

    # Deactivate and re-sync -> job should be removed
    active.is_active = False
    db_session.commit()
    remaining_ids = sync_interest_region_jobs(
        scheduler,
        db_session,
        session_factory=db_session_factory,
        use_fixture=True,
        output_dir=tmp_path,
    )
    assert remaining_ids == []
    assert list_scheduled_jobs(scheduler) == []
