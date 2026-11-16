"""Weekly report pipeline execution and manual trigger."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.collector import sync_buildings
from backend.exclusion import apply_exclusion_filter
from backend.jobs.diff import (
    compute_building_diff,
    format_region_code,
    parse_region_code,
)
from backend.report import generate_reports
from backend.stage import evaluate_building
from shared.database import SessionLocal
from shared.models import Building, InterestRegion, ReportRun
from shared.schemas import BuildingSyncRequest

DEFAULT_REPORT_DIR = Path("reports")


@contextmanager
def _session_scope(db: Session | None) -> Iterator[Session]:
    if db is not None:
        yield db
        return
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def run_weekly_pipeline(
    region_code: str,
    db: Session | None = None,
    *,
    use_fixture: bool = False,
    output_dir: str | Path | None = None,
    include_excluded: bool = False,
    service_key: str | None = None,
    reference_date: date | None = None,
    skip_collect: bool = False,
) -> ReportRun:
    """Execute collect -> stage/score -> diff -> Excel & PDF report -> save ReportRun."""
    sigungu_cd, bjdong_cd = parse_region_code(region_code)
    norm_region_code = format_region_code(sigungu_cd, bjdong_cd)

    with _session_scope(db) as session:
        if not skip_collect:
            sync_request = BuildingSyncRequest(
                sigungu_cd=sigungu_cd,
                bjdong_cd=bjdong_cd,
                use_fixture=use_fixture,
            )
            sync_buildings(session, sync_request, service_key=service_key)

        # Re-evaluate stage and priority score for all buildings in the region
        region_stmt = select(Building).where(Building.sigungu_cd == sigungu_cd)
        if bjdong_cd != "00000":
            region_stmt = region_stmt.where(Building.bjdong_cd == bjdong_cd)
        for building in session.scalars(region_stmt).all():
            new_stage, new_score = evaluate_building(building, reference_date=reference_date)
            building.stage = new_stage
            building.priority_score = new_score
        session.flush()

        # Query target buildings (excluding active exclusions unless include_excluded=True)
        target_stmt = select(Building).where(Building.sigungu_cd == sigungu_cd)
        if bjdong_cd != "00000":
            target_stmt = target_stmt.where(Building.bjdong_cd == bjdong_cd)
        target_stmt = apply_exclusion_filter(target_stmt, include_excluded=include_excluded)
        target_stmt = target_stmt.order_by(
            Building.priority_score.desc(), Building.mgm_pmsrgst_pk.asc()
        )
        target_buildings = list(session.scalars(target_stmt).all())

        # Fetch most recent previous ReportRun for diff computation
        previous_run = session.scalar(
            select(ReportRun)
            .where(ReportRun.region_code == norm_region_code)
            .order_by(ReportRun.run_at.desc(), ReportRun.id.desc())
            .limit(1)
        )
        diff = compute_building_diff(target_buildings, previous_run)

        # Generate Excel and PDF reports
        resolved_output_dir = Path(output_dir) if output_dir is not None else DEFAULT_REPORT_DIR
        region_tag = sigungu_cd if bjdong_cd == "00000" else f"{sigungu_cd}_{bjdong_cd}"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        report_result = generate_reports(
            db=session,
            output_dir=resolved_output_dir,
            sigungu_cd=sigungu_cd,
            bjdong_cd=bjdong_cd,
            include_excluded=include_excluded,
            formats=("excel", "pdf"),
            reference_date=reference_date.isoformat() if reference_date else None,
            file_prefix=f"weekly_{region_tag}_{stamp}",
        )

        report_run = ReportRun(
            region_code=norm_region_code,
            excel_path=str(report_result.excel_path) if report_result.excel_path else None,
            pdf_path=str(report_result.pdf_path) if report_result.pdf_path else None,
            total_count=report_result.target_count,
            new_count=len(diff["new_buildings"]),
            stage_changed_count=len(diff["stage_changed_buildings"]),
            diff_json=diff,
        )
        session.add(report_run)
        session.commit()
        session.refresh(report_run)
        return report_run


def run_all_active_regions(
    db: Session | None = None,
    *,
    use_fixture: bool = False,
    output_dir: str | Path | None = None,
    include_excluded: bool = False,
    service_key: str | None = None,
    reference_date: date | None = None,
    skip_collect: bool = False,
) -> list[ReportRun]:
    """Run the weekly report pipeline for every active InterestRegion."""
    with _session_scope(db) as session:
        regions = list(
            session.scalars(
                select(InterestRegion)
                .where(InterestRegion.is_active.is_(True))
                .order_by(InterestRegion.id.asc())
            ).all()
        )
        runs: list[ReportRun] = []
        for region in regions:
            code = format_region_code(region.sigungu_cd, region.bjdong_cd)
            run = run_weekly_pipeline(
                code,
                db=session,
                use_fixture=use_fixture,
                output_dir=output_dir,
                include_excluded=include_excluded,
                service_key=service_key,
                reference_date=reference_date,
                skip_collect=skip_collect,
            )
            runs.append(run)
        return runs
