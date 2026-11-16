"""Unit tests for backend/exclusion service and query helpers."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from backend.exclusion import (
    BuildingNotFoundError,
    InvalidCsvError,
    NotExcludedError,
    apply_exclusion_filter,
    apply_only_excluded_filter,
    bulk_exclude_from_csv,
    exclude_building,
    get_active_exclusion,
    get_active_exclusion_map,
    get_building_exclusion_history,
    is_building_excluded,
    list_exclusions,
    restore_building,
)
from shared.database import Base, create_db_engine
from shared.enums import BuildingStage, ExclusionStatus
from shared.models import Building


@pytest.fixture()
def db_session() -> Session:
    engine = create_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed_buildings(db: Session) -> list[Building]:
    buildings = [
        Building(
            mgm_pmsrgst_pk="PK-001",
            sigungu_cd="41135",
            bjdong_cd="10300",
            plat_plc="경기도 성남시 분당구 정자동 100",
            bld_nm="정자타워",
            main_purps_cd_nm="공동주택",
            hhld_cnt=120,
            tot_area=15000.0,
            stage=BuildingStage.NEAR_COMPLETION,
            priority_score=85.0,
        ),
        Building(
            mgm_pmsrgst_pk="PK-002",
            sigungu_cd="41135",
            bjdong_cd="10300",
            plat_plc="경기도 성남시 분당구 서현동 200",
            bld_nm="서현프라자",
            main_purps_cd_nm="업무시설",
            hhld_cnt=0,
            tot_area=8000.0,
            stage=BuildingStage.UNDER_CONSTRUCTION,
            priority_score=65.0,
        ),
        Building(
            mgm_pmsrgst_pk="PK-003",
            sigungu_cd="41135",
            bjdong_cd="10500",
            plat_plc="경기도 성남시 분당구 판교동 300",
            bld_nm="판교빌리지",
            main_purps_cd_nm="공동주택",
            hhld_cnt=50,
            tot_area=5500.0,
            stage=BuildingStage.PERMITTED,
            priority_score=40.0,
        ),
        Building(
            mgm_pmsrgst_pk="PK-004",
            sigungu_cd="41135",
            bjdong_cd="10500",
            plat_plc="경기도 성남시 분당구 야탑동 400",
            bld_nm="야탑오피스",
            main_purps_cd_nm="근린생활시설",
            hhld_cnt=0,
            tot_area=2000.0,
            stage=BuildingStage.START_SCHEDULED,
            priority_score=30.0,
        ),
    ]
    db.add_all(buildings)
    db.commit()
    return buildings


def test_exclude_and_get_history(db_session: Session) -> None:
    _seed_buildings(db_session)

    entry = exclude_building(
        db_session,
        mgm_pmsrgst_pk="PK-001",
        actor="kim.sales",
        status=ExclusionStatus.TELECOM_DONE_FIELD,
        reason="현장 방문 시 광케이블 개통 확인",
        evidence="/uploads/evidence/pk001.jpg",
    )

    assert entry.id is not None
    assert entry.mgm_pmsrgst_pk == "PK-001"
    assert entry.actor == "kim.sales"
    assert entry.status == ExclusionStatus.TELECOM_DONE_FIELD
    assert entry.reason == "현장 방문 시 광케이블 개통 확인"
    assert entry.evidence == "/uploads/evidence/pk001.jpg"
    assert entry.is_active is True
    assert entry.created_at is not None
    assert entry.restored_at is None
    assert entry.restored_by is None

    assert is_building_excluded(db_session, "PK-001") is True
    assert is_building_excluded(db_session, "PK-002") is False

    history = get_building_exclusion_history(db_session, "PK-001")
    assert len(history) == 1
    assert history[0].id == entry.id


def test_exclude_missing_building_raises(db_session: Session) -> None:
    with pytest.raises(BuildingNotFoundError):
        exclude_building(
            db_session,
            mgm_pmsrgst_pk="NON-EXISTENT",
            actor="admin",
            status=ExclusionStatus.NOT_TARGET,
        )


def test_re_exclude_supersedes_previous_active(db_session: Session) -> None:
    _seed_buildings(db_session)

    first = exclude_building(
        db_session,
        mgm_pmsrgst_pk="PK-001",
        actor="user1",
        status=ExclusionStatus.ON_HOLD,
        reason="임시 보류",
    )
    second = exclude_building(
        db_session,
        mgm_pmsrgst_pk="PK-001",
        actor="user2",
        status=ExclusionStatus.NOT_TARGET,
        reason="공공임대 비대상 확정",
    )

    db_session.refresh(first)
    assert first.is_active is False
    assert first.restored_by == "user2"
    assert first.restored_at is not None

    assert second.is_active is True
    active = get_active_exclusion(db_session, "PK-001")
    assert active is not None
    assert active.id == second.id

    active_list = list_exclusions(db_session, active_only=True)
    assert len(active_list) == 1
    assert active_list[0].id == second.id

    history = get_building_exclusion_history(db_session, "PK-001")
    assert len(history) == 2
    assert [h.id for h in history] == [second.id, first.id]


def test_restore_building_and_errors(db_session: Session) -> None:
    _seed_buildings(db_session)

    with pytest.raises(BuildingNotFoundError):
        restore_building(db_session, "NON-EXISTENT", restored_by="admin")

    with pytest.raises(NotExcludedError):
        restore_building(db_session, "PK-001", restored_by="admin")

    exclude_building(
        db_session,
        mgm_pmsrgst_pk="PK-001",
        actor="user1",
        status=ExclusionStatus.ON_HOLD,
        reason="보류",
    )
    restored = restore_building(db_session, "PK-001", restored_by="manager1")

    assert restored.is_active is False
    assert restored.restored_by == "manager1"
    assert restored.restored_at is not None
    assert is_building_excluded(db_session, "PK-001") is False

    # Restoring again should raise NotExcludedError
    with pytest.raises(NotExcludedError):
        restore_building(db_session, "PK-001", restored_by="manager1")


def test_list_exclusions_filters(db_session: Session) -> None:
    _seed_buildings(db_session)

    exclude_building(db_session, "PK-001", actor="u1", status=ExclusionStatus.TELECOM_DONE_FIELD)
    exclude_building(db_session, "PK-002", actor="u1", status=ExclusionStatus.TELECOM_DONE_SYSTEM)
    exclude_building(db_session, "PK-003", actor="u1", status=ExclusionStatus.NOT_TARGET)
    restore_building(db_session, "PK-003", restored_by="u2")

    assert len(list_exclusions(db_session, active_only=True)) == 2
    assert len(list_exclusions(db_session, active_only=False)) == 3

    field_only = list_exclusions(db_session, status=ExclusionStatus.TELECOM_DONE_FIELD, active_only=True)
    assert [x.mgm_pmsrgst_pk for x in field_only] == ["PK-001"]

    not_target_all = list_exclusions(db_session, status=ExclusionStatus.NOT_TARGET, active_only=False)
    assert [x.mgm_pmsrgst_pk for x in not_target_all] == ["PK-003"]


def test_apply_exclusion_filter_helpers(db_session: Session) -> None:
    _seed_buildings(db_session)

    exclude_building(db_session, "PK-001", actor="u1", status=ExclusionStatus.TELECOM_DONE_FIELD)
    exclude_building(db_session, "PK-003", actor="u1", status=ExclusionStatus.ON_HOLD)
    restore_building(db_session, "PK-003", restored_by="u2")

    # SQLAlchemy 2.0 select(Building)
    active_pks = db_session.scalars(
        apply_exclusion_filter(select(Building.mgm_pmsrgst_pk), include_excluded=False).order_by(
            Building.mgm_pmsrgst_pk
        )
    ).all()
    assert active_pks == ["PK-002", "PK-003", "PK-004"]

    all_pks = db_session.scalars(
        apply_exclusion_filter(select(Building.mgm_pmsrgst_pk), include_excluded=True).order_by(
            Building.mgm_pmsrgst_pk
        )
    ).all()
    assert all_pks == ["PK-001", "PK-002", "PK-003", "PK-004"]

    excluded_pks = db_session.scalars(
        apply_only_excluded_filter(select(Building.mgm_pmsrgst_pk))
    ).all()
    assert excluded_pks == ["PK-001"]

    # Aggregate count query compatibility
    active_count = db_session.scalar(
        apply_exclusion_filter(select(func.count(Building.mgm_pmsrgst_pk)), include_excluded=False)
    )
    assert active_count == 3

    # Legacy Session.query compatibility
    legacy_pks = [
        b.mgm_pmsrgst_pk
        for b in apply_exclusion_filter(db_session.query(Building), include_excluded=False)
        .order_by(Building.mgm_pmsrgst_pk)
        .all()
    ]
    assert legacy_pks == ["PK-002", "PK-003", "PK-004"]

    # Active exclusion map
    excl_map = get_active_exclusion_map(db_session, ["PK-001", "PK-002", "PK-003"])
    assert set(excl_map.keys()) == {"PK-001"}
    assert excl_map["PK-001"].status == ExclusionStatus.TELECOM_DONE_FIELD


def test_bulk_exclude_from_csv_pk_and_address_matching(db_session: Session) -> None:
    _seed_buildings(db_session)

    csv_text = (
        "mgm_pmsrgst_pk,대지위치,건물명,사유,증빙\n"
        "PK-001,,,자사 시스템 일괄 반영,SYS-2026-01\n"
        ",경기도 성남시 분당구   서현동 200,서현프라자,주소/건물명 매칭,\n"
        ",경기도 성남시 분당구 판교동 300,,주소 단독 매칭,\n"
        ",경기도 성남시 분당구 없는주소 999,없는건물,,\n"
        ",,,,\n"
    )

    resp = bulk_exclude_from_csv(
        db_session,
        csv_content=csv_text.encode("utf-8-sig"),
        actor="batch_user",
        status=ExclusionStatus.TELECOM_DONE_SYSTEM,
    )

    assert resp.total_rows == 5
    assert resp.excluded_count == 3
    assert resp.not_found_count == 1
    assert resp.error_count == 1

    assert resp.results[0].status == "excluded"
    assert resp.results[0].matched_pk == "PK-001"
    assert resp.results[1].status == "excluded"
    assert resp.results[1].matched_pk == "PK-002"
    assert resp.results[2].status == "excluded"
    assert resp.results[2].matched_pk == "PK-003"
    assert resp.results[3].status == "not_found"
    assert resp.results[4].status == "error"

    assert is_building_excluded(db_session, "PK-001") is True
    assert is_building_excluded(db_session, "PK-002") is True
    assert is_building_excluded(db_session, "PK-003") is True
    assert is_building_excluded(db_session, "PK-004") is False


def test_bulk_exclude_cp949_and_ambiguous_and_invalid_csv(db_session: Session) -> None:
    _seed_buildings(db_session)
    # Add another building with same bld_nm to test ambiguous match
    db_session.add(
        Building(
            mgm_pmsrgst_pk="PK-005",
            sigungu_cd="41135",
            bjdong_cd="10500",
            plat_plc="경기도 성남시 분당구 구미동 500",
            bld_nm="야탑오피스",
            stage=BuildingStage.PERMITTED,
            priority_score=10.0,
        )
    )
    db_session.commit()

    csv_cp949 = "건물명,상태\n야탑오피스,TELECOM_DONE_SYSTEM\n정자타워,INVALID_STATUS\n".encode("cp949")
    resp = bulk_exclude_from_csv(db_session, csv_content=csv_cp949, actor="cp949_user")
    assert resp.total_rows == 2
    assert resp.error_count == 2
    assert "Ambiguous match" in (resp.results[0].detail or "")
    assert "Invalid exclusion status" in (resp.results[1].detail or "")

    with pytest.raises(InvalidCsvError):
        bulk_exclude_from_csv(db_session, csv_content=b"", actor="admin")
