"""Unit tests for backend.region."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from backend.region import (
    ensure_regions_seeded,
    get_region_by_code,
    list_emd,
    list_sido,
    list_sigungu,
    load_legal_dong_file,
    load_regions_from_file,
    parse_legal_dong_row,
    seed_regions,
    to_api_params,
)
from shared.database import Base, create_db_engine
from shared.models import Region


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


def test_seed_regions_and_idempotency(db_session: Session) -> None:
    inserted = seed_regions(db_session)
    assert inserted > 80

    # Second call via ensure_regions_seeded should do nothing
    assert ensure_regions_seeded(db_session) == 0

    sido_list = list_sido(db_session)
    assert len(sido_list) == 17
    sido_names = {r.sido_name for r in sido_list}
    assert "서울특별시" in sido_names
    assert "경기도" in sido_names
    assert "세종특별자치시" in sido_names
    assert "강원특별자치도" in sido_names
    assert "전북특별자치도" in sido_names


def test_hierarchy_lookup_bundang_and_sejong(db_session: Session) -> None:
    seed_regions(db_session)

    # 경기도 (41) -> 성남시 분당구 (41135)
    gg_sigungu = list_sigungu(db_session, "41")
    sigungu_cds = {r.sigungu_cd for r in gg_sigungu}
    assert "41135" in sigungu_cds

    bundang = next(r for r in gg_sigungu if r.sigungu_cd == "41135")
    assert bundang.sigungu_name == "성남시 분당구"
    assert bundang.bjdong_cd == "00000"

    # 분당구 (41135) -> 읍/면/동
    bundang_emd = list_emd(db_session, "41135")
    emd_names = {r.emd_name for r in bundang_emd}
    assert {"분당동", "수내동", "정자동", "판교동", "삼평동", "백현동"}.issubset(emd_names)
    assert all(r.bjdong_cd != "00000" for r in bundang_emd)

    # 세종특별자치시 (36)
    sejong_sigungu = list_sigungu(db_session, "36")
    assert len(sejong_sigungu) == 1
    assert sejong_sigungu[0].code == "3611000000"
    sejong_emd = list_emd(db_session, "36110")
    assert any(r.emd_name == "반곡동" for r in sejong_emd)


def test_parse_excludes_abolished_and_splits_names() -> None:
    assert parse_legal_dong_row("1111010100", "서울특별시 종로구 청운동", "폐지") is None
    assert parse_legal_dong_row("invalid", "서울특별시", "존재") is None

    seoul_emd = parse_legal_dong_row("1168010100", "서울특별시 강남구 역삼동", "존재")
    assert seoul_emd is not None
    assert (seoul_emd.sido_name, seoul_emd.sigungu_name, seoul_emd.emd_name) == (
        "서울특별시",
        "강남구",
        "역삼동",
    )

    bundang_emd = parse_legal_dong_row("4113510300", "경기도 성남시 분당구 정자동", "존재")
    assert bundang_emd is not None
    assert (bundang_emd.sido_name, bundang_emd.sigungu_name, bundang_emd.emd_name) == (
        "경기도",
        "성남시 분당구",
        "정자동",
    )

    ri_row = parse_legal_dong_row("4182025021", "경기도 가평군 가평읍 읍내리", "존재")
    assert ri_row is not None
    assert (ri_row.sido_name, ri_row.sigungu_name, ri_row.emd_name) == (
        "경기도",
        "가평군",
        "가평읍 읍내리",
    )


def test_load_tsv_and_csv_files(db_session: Session, tmp_path: Path) -> None:
    tsv_path = tmp_path / "bjdong.txt"
    tsv_content = (
        "법정동코드\t법정동명\t폐지여부\n"
        "4182000000\t경기도 가평군\t존재\n"
        "4182025000\t경기도 가평군 가평읍\t존재\n"
        "4182025021\t경기도 가평군 가평읍 읍내리\t존재\n"
        "4182025099\t경기도 가평군 가평읍 옛리\t폐지\n"
    )
    tsv_path.write_bytes(tsv_content.encode("cp949"))

    parsed = load_legal_dong_file(tsv_path)
    assert len(parsed) == 3
    assert all(p.code != "4182025099" for p in parsed)

    loaded = load_regions_from_file(db_session, tsv_path)
    assert loaded == 3

    # Default list_emd excludes 리 (last 2 digits != 00)
    emd_only = list_emd(db_session, "41820", include_ri=False)
    assert [r.emd_name for r in emd_only] == ["가평읍"]

    # include_ri=True includes 리
    with_ri = list_emd(db_session, "41820", include_ri=True)
    assert len(with_ri) == 2

    # CSV UTF-8-BOM support
    csv_path = tmp_path / "bjdong.csv"
    csv_path.write_text(
        "법정동코드,법정동명,폐지여부\n1100000000,서울특별시,존재\n1111000000,서울특별시 종로구,폐지\n",
        encoding="utf-8-sig",
    )
    csv_parsed = load_legal_dong_file(csv_path)
    assert len(csv_parsed) == 1
    assert csv_parsed[0].code == "1100000000"


def test_to_api_params(db_session: Session) -> None:
    seed_regions(db_session)

    # Whole sigungu (10-digit)
    params_sigungu = to_api_params("4113500000")
    assert params_sigungu.sigunguCd == "41135"
    assert params_sigungu.bjdongCd == "00000"

    # Whole sigungu (5-digit shorthand)
    params_short = to_api_params("41135")
    assert params_short.sigunguCd == "41135"
    assert params_short.bjdongCd == "00000"

    # Specific 읍/면/동 (10-digit)
    params_emd = to_api_params("4113510300")
    assert params_emd.sigunguCd == "41135"
    assert params_emd.bjdongCd == "10300"

    # Region ORM model
    region = get_region_by_code(db_session, "4113510800")
    assert region is not None
    params_orm = to_api_params(region)
    assert params_orm.sigunguCd == "41135"
    assert params_orm.bjdongCd == "10800"

    # Invalid inputs
    with pytest.raises(ValueError):
        to_api_params("4113")
    with pytest.raises(ValueError):
        to_api_params("abcdefghij")


def test_incheon_2026_reorganization_and_existing_db_update(db_session: Session) -> None:
    # Simulate an existing DB with pre-2026-07-01 Incheon districts
    db_session.add_all(
        [
            Region(
                code="2800000000",
                sido_cd="28",
                sigungu_cd="28000",
                bjdong_cd="00000",
                sido_name="인천광역시",
                sigungu_name=None,
                emd_name=None,
                is_active=True,
            ),
            Region(
                code="2811000000",
                sido_cd="28",
                sigungu_cd="28110",
                bjdong_cd="00000",
                sido_name="인천광역시",
                sigungu_name="중구",
                emd_name=None,
                is_active=True,
            ),
            Region(
                code="2814000000",
                sido_cd="28",
                sigungu_cd="28140",
                bjdong_cd="00000",
                sido_name="인천광역시",
                sigungu_name="동구",
                emd_name=None,
                is_active=True,
            ),
            Region(
                code="2826000000",
                sido_cd="28",
                sigungu_cd="28260",
                bjdong_cd="00000",
                sido_name="인천광역시",
                sigungu_name="서구",
                emd_name=None,
                is_active=True,
            ),
        ]
    )
    db_session.commit()

    # ensure_regions_seeded should detect old Incheon rows and apply reorganization
    updated = ensure_regions_seeded(db_session)
    assert updated > 0

    incheon_sigungu = list_sigungu(db_session, "28")
    names = {r.sigungu_name for r in incheon_sigungu}
    assert {
        "제물포구",
        "영종구",
        "미추홀구",
        "연수구",
        "남동구",
        "부평구",
        "계양구",
        "서해구",
        "검단구",
        "강화군",
        "옹진군",
    } == names
    assert "중구" not in names
    assert "동구" not in names
    assert "서구" not in names

    # Old 중구 & 동구 should be marked is_active=False
    old_junggu = db_session.get(Region, "2811000000")
    old_donggu = db_session.get(Region, "2814000000")
    assert old_junggu is not None and old_junggu.is_active is False
    assert old_donggu is not None and old_donggu.is_active is False

    # 서해구 (28260) should be updated from 서구 -> 서해구
    seohae = db_session.get(Region, "2826000000")
    assert seohae is not None and seohae.sigungu_name == "서해구"

    # Check 읍/면/동 under new districts
    assert any(r.emd_name == "만석동" for r in list_emd(db_session, "28150"))
    assert any(r.emd_name == "운서동" for r in list_emd(db_session, "28160"))
    assert any(r.emd_name == "청라동" for r in list_emd(db_session, "28260"))
    assert any(r.emd_name == "아라동" for r in list_emd(db_session, "28280"))
