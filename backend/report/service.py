"""Report service orchestrating DB queries (with exclusion filtering) and Excel/PDF generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.exclusion import (
    apply_exclusion_filter,
    apply_only_excluded_filter,
    get_active_exclusion_map,
)
from backend.report.excel import generate_excel_report
from backend.report.pdf import generate_pdf_report
from shared.enums import BuildingStage
from shared.models import Building, Region


@dataclass
class ReportDataset:
    buildings: list[Building]
    excluded_rows: list[dict[str, Any]]
    region_name: str
    reference_date: str

    @property
    def target_count(self) -> int:
        return len(self.buildings)

    @property
    def near_completion_count(self) -> int:
        return sum(1 for b in self.buildings if b.stage == BuildingStage.NEAR_COMPLETION)

    @property
    def excluded_count(self) -> int:
        return len(self.excluded_rows)


@dataclass
class GeneratedReportResult:
    excel_path: Path | None
    pdf_path: Path | None
    target_count: int
    near_completion_count: int
    excluded_count: int
    region_name: str
    reference_date: str


def _resolve_region_name(db: Session, sigungu_cd: str | None, bjdong_cd: str | None) -> str:
    if not sigungu_cd:
        return "전체 지역"

    bjd = bjdong_cd or "00000"
    region = db.scalar(
        select(Region).where(
            Region.sigungu_cd == sigungu_cd,
            Region.bjdong_cd == bjd,
        )
    )
    if region is None and bjd != "00000":
        region = db.scalar(
            select(Region).where(
                Region.sigungu_cd == sigungu_cd,
                Region.bjdong_cd == "00000",
            )
        )
    if region is None:
        return f"{sigungu_cd}-{bjd}" if bjd != "00000" else sigungu_cd

    parts = [p for p in (region.sido_name, region.sigungu_name, region.emd_name) if p]
    code_label = f"{sigungu_cd}" if bjd == "00000" else f"{sigungu_cd}-{bjd}"
    return f"{' '.join(parts)} ({code_label})"


def _apply_region_and_stage_filters(
    stmt: Any,
    sigungu_cd: str | None,
    bjdong_cd: str | None,
    stages: Sequence[BuildingStage] | None = None,
) -> Any:
    if sigungu_cd:
        stmt = stmt.where(Building.sigungu_cd == sigungu_cd)
    if bjdong_cd and bjdong_cd != "00000":
        stmt = stmt.where(Building.bjdong_cd == bjdong_cd)
    if stages:
        stmt = stmt.where(Building.stage.in_(list(stages)))
    return stmt


def fetch_report_dataset(
    db: Session,
    sigungu_cd: str | None = None,
    bjdong_cd: str | None = None,
    stages: Sequence[BuildingStage] | None = None,
    include_excluded: bool = False,
    region_name: str | None = None,
    reference_date: str | None = None,
) -> ReportDataset:
    """Query target buildings and currently excluded buildings using backend/exclusion helpers."""
    target_stmt = select(Building)
    target_stmt = _apply_region_and_stage_filters(target_stmt, sigungu_cd, bjdong_cd, stages)
    target_stmt = apply_exclusion_filter(target_stmt, include_excluded=include_excluded)
    target_stmt = target_stmt.order_by(Building.priority_score.desc(), Building.mgm_pmsrgst_pk.asc())
    buildings = list(db.scalars(target_stmt).all())

    excl_stmt = select(Building)
    excl_stmt = _apply_region_and_stage_filters(excl_stmt, sigungu_cd, bjdong_cd, stages=None)
    excl_stmt = apply_only_excluded_filter(excl_stmt)
    excl_stmt = excl_stmt.order_by(Building.priority_score.desc(), Building.mgm_pmsrgst_pk.asc())
    excluded_buildings = list(db.scalars(excl_stmt).all())

    excl_map = get_active_exclusion_map(db, [b.mgm_pmsrgst_pk for b in excluded_buildings])
    excluded_rows: list[dict[str, Any]] = []
    for b in excluded_buildings:
        hist = excl_map.get(b.mgm_pmsrgst_pk)
        excluded_rows.append(
            {
                "mgm_pmsrgst_pk": b.mgm_pmsrgst_pk,
                "bld_nm": b.bld_nm,
                "plat_plc": b.plat_plc,
                "main_purps_cd_nm": b.main_purps_cd_nm,
                "stage": b.stage,
                "status": hist.status if hist else None,
                "reason": hist.reason if hist else None,
                "evidence": hist.evidence if hist else None,
                "actor": hist.actor if hist else None,
                "created_at": hist.created_at if hist else None,
            }
        )

    resolved_name = region_name or _resolve_region_name(db, sigungu_cd, bjdong_cd)
    ref_date = reference_date or date.today().isoformat()
    return ReportDataset(
        buildings=buildings,
        excluded_rows=excluded_rows,
        region_name=resolved_name,
        reference_date=ref_date,
    )


def generate_reports(
    db: Session,
    output_dir: str | Path,
    sigungu_cd: str | None = None,
    bjdong_cd: str | None = None,
    stages: Sequence[BuildingStage] | None = None,
    include_excluded: bool = False,
    formats: Sequence[str] = ("excel", "pdf"),
    region_name: str | None = None,
    reference_date: str | None = None,
    file_prefix: str | None = None,
) -> GeneratedReportResult:
    """Query dataset once and generate Excel and/or PDF reports with identical target counts."""
    dataset = fetch_report_dataset(
        db=db,
        sigungu_cd=sigungu_cd,
        bjdong_cd=bjdong_cd,
        stages=stages,
        include_excluded=include_excluded,
        region_name=region_name,
        reference_date=reference_date,
    )

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    region_tag = sigungu_cd or "all"
    if bjdong_cd and bjdong_cd != "00000":
        region_tag = f"{region_tag}_{bjdong_cd}"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = file_prefix or f"report_{region_tag}_{stamp}"

    fmt_set = {f.lower() for f in formats}
    excel_path: Path | None = None
    pdf_path: Path | None = None

    if "excel" in fmt_set or "xlsx" in fmt_set:
        excel_path = generate_excel_report(
            buildings=dataset.buildings,
            excluded_rows=dataset.excluded_rows,
            output_path=out_dir / f"{prefix}.xlsx",
            region_name=dataset.region_name,
            reference_date=dataset.reference_date,
        )

    if "pdf" in fmt_set:
        pdf_path = generate_pdf_report(
            buildings=dataset.buildings,
            excluded_rows=dataset.excluded_rows,
            output_path=out_dir / f"{prefix}.pdf",
            region_name=dataset.region_name,
            reference_date=dataset.reference_date,
        )

    return GeneratedReportResult(
        excel_path=excel_path,
        pdf_path=pdf_path,
        target_count=dataset.target_count,
        near_completion_count=dataset.near_completion_count,
        excluded_count=dataset.excluded_count,
        region_name=dataset.region_name,
        reference_date=dataset.reference_date,
    )
