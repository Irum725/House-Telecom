"""Unit and integration tests for backend/report/."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest
from openpyxl import load_workbook
from sqlalchemy.orm import Session, sessionmaker

from backend.exclusion import exclude_building, restore_building
from backend.report import (
    REQUIRED_SHEETS,
    SHEET_EXCLUDED,
    SHEET_NEAR_COMPLETION,
    SHEET_SUMMARY,
    SHEET_TARGETS,
    build_report_html,
    generate_reports,
)
from shared.database import Base, create_db_engine
from shared.enums import BuildingStage, ExclusionStatus
from shared.models import Building, Region


@pytest.fixture()
def db_session() -> Session:
    engine = create_db_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed_sample_data(db: Session) -> list[Building]:
    db.add(
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
    buildings = [
        Building(
            mgm_pmsrgst_pk="PK-001",
            sigungu_cd="41135",
            bjdong_cd="10900",
            plat_plc="경기도 성남시 분당구 정자동 101",
            bld_nm="분당 센트럴타워",
            main_purps_cd_nm="공동주택",
            tot_area=12500.5,
            hhld_cnt=120,
            dong_cnt=2,
            arch_pms_day="20250110",
            stcns_sched_day="20250301",
            real_stcns_day="20250315",
            stage=BuildingStage.NEAR_COMPLETION,
            priority_score=92.5,
        ),
        Building(
            mgm_pmsrgst_pk="PK-002",
            sigungu_cd="41135",
            bjdong_cd="10900",
            plat_plc="경기도 성남시 분당구 정자동 202",
            bld_nm="정자 오피스빌딩",
            main_purps_cd_nm="업무시설",
            tot_area=6400.0,
            hhld_cnt=0,
            dong_cnt=1,
            arch_pms_day="20250401",
            stcns_sched_day="20250601",
            real_stcns_day="20250610",
            stage=BuildingStage.UNDER_CONSTRUCTION,
            priority_score=74.0,
        ),
        Building(
            mgm_pmsrgst_pk="PK-003",
            sigungu_cd="41135",
            bjdong_cd="10500",
            plat_plc="경기도 성남시 분당구 서현동 303",
            bld_nm="서현 근린빌딩",
            main_purps_cd_nm="근린생활시설",
            tot_area=1800.0,
            hhld_cnt=0,
            dong_cnt=1,
            arch_pms_day="20260105",
            stage=BuildingStage.PERMITTED,
            priority_score=41.0,
        ),
        Building(
            mgm_pmsrgst_pk="PK-004",
            sigungu_cd="41135",
            bjdong_cd="10500",
            plat_plc="경기도 성남시 분당구 서현동 404",
            bld_nm="서현 푸르지오",
            main_purps_cd_nm="공동주택",
            tot_area=21000.0,
            hhld_cnt=240,
            dong_cnt=3,
            arch_pms_day="20240501",
            real_stcns_day="20240701",
            stage=BuildingStage.NEAR_COMPLETION,
            priority_score=96.0,
        ),
    ]
    db.add_all(buildings)
    db.commit()
    return buildings


def test_excel_and_pdf_generation_with_exclusion_and_matching_counts(
    db_session: Session, tmp_path: Path
) -> None:
    _seed_sample_data(db_session)
    exclude_building(
        db_session,
        mgm_pmsrgst_pk="PK-004",
        actor="tester",
        status=ExclusionStatus.TELECOM_DONE_FIELD,
        reason="현장 개통 완료 확인",
        evidence="photo_004.jpg",
    )

    result = generate_reports(
        db=db_session,
        output_dir=tmp_path,
        sigungu_cd="41135",
        bjdong_cd="00000",
        reference_date="2026-11-16",
        file_prefix="bundang_test",
    )

    assert result.excel_path is not None and result.excel_path.exists()
    assert result.pdf_path is not None and result.pdf_path.exists()
    assert result.excel_path.stat().st_size > 0
    assert result.pdf_path.stat().st_size > 0

    # 4 total seeded, 1 excluded -> 3 active targets, 1 near completion (PK-001)
    assert result.target_count == 3
    assert result.near_completion_count == 1
    assert result.excluded_count == 1

    # Verify Excel workbook structure, formatting, and counts
    wb = load_workbook(result.excel_path)
    assert wb.sheetnames == list(REQUIRED_SHEETS)

    ws_summary = wb[SHEET_SUMMARY]
    assert ws_summary["B5"].value == 3
    assert ws_summary["B6"].value == 1
    assert ws_summary["B7"].value == 1

    ws_targets = wb[SHEET_TARGETS]
    assert ws_targets.freeze_panes == "A2"
    assert ws_targets.auto_filter.ref == "A1:P4"
    assert ws_targets.cell(row=1, column=14).value == "예상준공월"
    # PK-001: real_stcns_day=20250315, tot_area=12500.5 -> +16 months -> 2026-07
    assert ws_targets.cell(row=2, column=14).value == "2026-07"
    # PK-002: real_stcns_day=20250610, tot_area=6400.0 -> +16 months -> 2026-10
    assert ws_targets.cell(row=3, column=14).value == "2026-10"
    # PK-003: no start date -> "-"
    assert ws_targets.cell(row=4, column=14).value == "-"
    cf_groups = list(ws_targets.conditional_formatting)
    assert len(cf_groups) == 1
    assert len(cf_groups[0].rules) == 5
    excel_target_pks = [
        ws_targets.cell(row=r, column=1).value for r in range(2, ws_targets.max_row + 1)
    ]
    assert excel_target_pks == ["PK-001", "PK-002", "PK-003"]
    assert "PK-004" not in excel_target_pks

    ws_near = wb[SHEET_NEAR_COMPLETION]
    assert ws_near.max_row - 1 == 1
    assert ws_near.cell(row=2, column=1).value == "PK-001"

    ws_excluded = wb[SHEET_EXCLUDED]
    assert ws_excluded.freeze_panes == "A2"
    assert ws_excluded.max_row - 1 == 1
    assert ws_excluded.cell(row=2, column=1).value == "PK-004"
    assert ws_excluded.cell(row=2, column=6).value == ExclusionStatus.TELECOM_DONE_FIELD.label_ko
    wb.close()

    # Verify PDF validity, Korean text rendering, and matching target count
    pdf_doc = fitz.open(result.pdf_path)
    assert pdf_doc.page_count >= 1
    full_text = "\n".join(page.get_text() for page in pdf_doc)
    fonts = pdf_doc[0].get_fonts()
    pdf_doc.close()

    assert len(fonts) > 0
    assert "신축 통신공사 사전파악 리포트" in full_text
    assert "경기도 성남시 분당구" in full_text
    assert f"총 대상 건수: {len(excel_target_pks)}건" in full_text

    compact_text = "".join(full_text.split())
    assert "분당센트럴타워" in compact_text
    assert "정자오피스빌딩" in compact_text
    assert "서현근린빌딩" in compact_text
    assert "서현푸르지오" not in compact_text


def test_restore_reappears_in_reports(db_session: Session, tmp_path: Path) -> None:
    _seed_sample_data(db_session)
    exclude_building(
        db_session,
        mgm_pmsrgst_pk="PK-004",
        actor="tester",
        status=ExclusionStatus.ON_HOLD,
        reason="보류",
    )
    restore_building(db_session, mgm_pmsrgst_pk="PK-004", restored_by="tester")

    result = generate_reports(
        db=db_session,
        output_dir=tmp_path,
        sigungu_cd="41135",
        file_prefix="restored_test",
    )
    assert result.target_count == 4
    assert result.near_completion_count == 2
    assert result.excluded_count == 0

    wb = load_workbook(result.excel_path)
    assert wb[SHEET_TARGETS].max_row - 1 == 4
    assert wb[SHEET_NEAR_COMPLETION].max_row - 1 == 2
    assert wb[SHEET_EXCLUDED].max_row - 1 == 0
    wb.close()


def test_empty_dataset_generates_valid_reports(db_session: Session, tmp_path: Path) -> None:
    result = generate_reports(
        db=db_session,
        output_dir=tmp_path,
        sigungu_cd="99999",
        file_prefix="empty_test",
    )
    assert result.target_count == 0
    assert result.excluded_count == 0
    assert result.excel_path is not None and result.excel_path.stat().st_size > 0
    assert result.pdf_path is not None and result.pdf_path.stat().st_size > 0

    wb = load_workbook(result.excel_path)
    assert wb.sheetnames == list(REQUIRED_SHEETS)
    wb.close()

    pdf_doc = fitz.open(result.pdf_path)
    assert pdf_doc.page_count >= 1
    text = pdf_doc[0].get_text()
    pdf_doc.close()
    assert "총 대상 건수: 0건" in text


def test_html_contains_svg_charts_and_noto_font() -> None:
    html_str = build_report_html(
        buildings=[],
        excluded_rows=[],
        region_name="경기도 성남시 분당구 (41135)",
        reference_date="2026-11-16",
    )
    assert "<svg" in html_str
    assert "Noto Sans KR" in html_str
    assert "경기도 성남시 분당구 (41135)" in html_str
