"""Region seeding, hierarchical lookup, and 건축HUB API parameter conversion."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.region.parser import ParsedRegion, load_legal_dong_file, parse_legal_dong_rows
from backend.region.seed_data import SEED_LEGAL_DONG_ROWS
from shared.models import Region
from shared.schemas import RegionApiParams


def upsert_parsed_regions(db: Session, parsed_regions: Iterable[ParsedRegion]) -> int:
    """Upsert parsed active regions into the Region table. Returns count processed."""
    items = list(parsed_regions)
    if not items:
        return 0

    codes = [item.code for item in items]
    existing_map: dict[str, Region] = {
        r.code: r
        for r in db.scalars(select(Region).where(Region.code.in_(codes))).all()
    }

    for item in items:
        existing = existing_map.get(item.code)
        if existing is None:
            db.add(
                Region(
                    code=item.code,
                    sido_cd=item.sido_cd,
                    sigungu_cd=item.sigungu_cd,
                    bjdong_cd=item.bjdong_cd,
                    sido_name=item.sido_name,
                    sigungu_name=item.sigungu_name,
                    emd_name=item.emd_name,
                    is_active=item.is_active,
                )
            )
        else:
            existing.sido_cd = item.sido_cd
            existing.sigungu_cd = item.sigungu_cd
            existing.bjdong_cd = item.bjdong_cd
            existing.sido_name = item.sido_name
            existing.sigungu_name = item.sigungu_name
            existing.emd_name = item.emd_name
            existing.is_active = item.is_active

    db.commit()
    return len(items)


def seed_regions(
    db: Session, rows: Iterable[tuple[str, str, str]] | None = None
) -> int:
    """Seed Region table from built-in SEED_LEGAL_DONG_ROWS (or provided rows).

    Active ('존재') rows are upserted with is_active=True (updating existing
    sigungu_name / emd_name / is_active if changed). Abolished ('폐지') rows
    deactivate any matching existing Region rows (is_active=False).
    """
    source_rows = list(SEED_LEGAL_DONG_ROWS if rows is None else rows)
    parsed = parse_legal_dong_rows(source_rows)
    count = upsert_parsed_regions(db, parsed)

    abolished_codes = [
        code.strip()
        for code, _, status in source_rows
        if status.strip() != "존재" and len(code.strip()) == 10 and code.strip().isdigit()
    ]
    if abolished_codes:
        existing_abolished = db.scalars(
            select(Region).where(Region.code.in_(abolished_codes), Region.is_active.is_(True))
        ).all()
        if existing_abolished:
            for region in existing_abolished:
                region.is_active = False
            db.commit()

    return count


def ensure_regions_seeded(db: Session) -> int:
    """Seed regions if empty or if Incheon 2026-07-01 reorganization is not yet applied."""
    count = db.scalar(select(func.count()).select_from(Region)) or 0
    if count == 0:
        return seed_regions(db)

    old_junggu = db.scalar(
        select(Region).where(Region.code == "2811000000", Region.is_active.is_(True))
    )
    jemulpo = db.scalar(
        select(Region).where(Region.code == "2815000000", Region.is_active.is_(True))
    )
    yeongjong_jungsan = db.get(Region, "2816014500")
    if old_junggu is not None or jemulpo is None or yeongjong_jungsan is None:
        return seed_regions(db)
    return 0


def load_regions_from_file(db: Session, file_path: str | Path) -> int:
    """Load full 법정동코드 TSV/CSV file into Region table, excluding 폐지 codes."""
    parsed = load_legal_dong_file(file_path)
    return upsert_parsed_regions(db, parsed)


def list_sido(db: Session) -> list[Region]:
    """Return all active 시/도 regions ordered by code."""
    stmt = (
        select(Region)
        .where(
            Region.is_active.is_(True),
            Region.sigungu_name.is_(None),
            Region.emd_name.is_(None),
        )
        .order_by(Region.code.asc())
    )
    return list(db.scalars(stmt).all())


def list_sigungu(db: Session, sido_cd: str) -> list[Region]:
    """Return all active 시/군/구 regions for a given 2-digit sido_cd."""
    stmt = (
        select(Region)
        .where(
            Region.is_active.is_(True),
            Region.sido_cd == sido_cd,
            Region.bjdong_cd == "00000",
            Region.sigungu_name.is_not(None),
            Region.emd_name.is_(None),
        )
        .order_by(Region.code.asc())
    )
    results = list(db.scalars(stmt).all())

    # Special case: 세종특별자치시 (sido_cd == "36") has no separate 구;
    # return the 3611000000 entry so 3-step UI selection works seamlessly.
    if not results and sido_cd == "36":
        sejong_stmt = (
            select(Region)
            .where(
                Region.is_active.is_(True),
                Region.code == "3611000000",
            )
            .order_by(Region.code.asc())
        )
        results = list(db.scalars(sejong_stmt).all())

    return results


def list_emd(db: Session, sigungu_cd: str, include_ri: bool = False) -> list[Region]:
    """Return all active 읍/면/동 regions for a given 5-digit sigungu_cd."""
    stmt = select(Region).where(
        Region.is_active.is_(True),
        Region.sigungu_cd == sigungu_cd,
        Region.bjdong_cd != "00000",
    )
    if not include_ri:
        stmt = stmt.where(Region.bjdong_cd.endswith("00"))
    stmt = stmt.order_by(Region.code.asc())
    return list(db.scalars(stmt).all())


def get_region_by_code(db: Session, code: str) -> Region | None:
    """Fetch a single active Region by 10-digit code."""
    stmt = select(Region).where(Region.code == code.strip(), Region.is_active.is_(True))
    return db.scalar(stmt)


def to_api_params(code_or_region: str | Region) -> RegionApiParams:
    """Convert a Region or 10-digit/5-digit code to 건축HUB API parameters.

    Returns RegionApiParams(sigunguCd=5 digits, bjdongCd=5 digits).
    When a whole 시군구 is selected (e.g. 4113500000 or 41135), bjdongCd is "00000".
    """
    if isinstance(code_or_region, Region):
        return RegionApiParams(
            sigunguCd=code_or_region.sigungu_cd,
            bjdongCd=code_or_region.bjdong_cd,
        )

    code = code_or_region.strip()
    if not code.isdigit():
        raise ValueError(f"Region code must be numeric: {code_or_region!r}")

    if len(code) == 10:
        return RegionApiParams(sigunguCd=code[:5], bjdongCd=code[5:10])
    if len(code) == 5:
        return RegionApiParams(sigunguCd=code, bjdongCd="00000")

    raise ValueError(
        f"Region code must be 10 digits (법정동코드) or 5 digits (시군구코드), got {code_or_region!r}"
    )
