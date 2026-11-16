"""Reports generation, history, and file download API router."""

import os
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.report import generate_reports
from shared.database import get_db
from shared.models import ReportRun
from shared.schemas import ReportGenerateRequest, ReportListResponse, ReportRunItem

router = APIRouter(prefix="/api/reports", tags=["reports"])

EXCEL_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PDF_MEDIA_TYPE = "application/pdf"


def _get_report_output_dir() -> Path:
    return Path(os.getenv("REPORT_OUTPUT_DIR", "./data/reports"))


@router.get("", response_model=ReportListResponse)
def list_reports(
    region_code: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> ReportListResponse:
    """List report run history, newest first."""
    stmt = select(ReportRun).order_by(ReportRun.run_at.desc(), ReportRun.id.desc())
    if region_code:
        stmt = stmt.where(ReportRun.region_code.like(f"{region_code}%"))
    rows = list(db.scalars(stmt).all())
    items = [ReportRunItem.model_validate(r) for r in rows]
    return ReportListResponse(items=items, total=len(items))


@router.post("/generate", response_model=ReportRunItem, status_code=201)
def generate_report_now(
    payload: ReportGenerateRequest,
    db: Session = Depends(get_db),
) -> ReportRunItem:
    """Generate Excel and/or PDF report immediately and record a ReportRun."""
    output_dir = _get_report_output_dir()
    result = generate_reports(
        db=db,
        output_dir=output_dir,
        sigungu_cd=payload.sigungu_cd,
        bjdong_cd=payload.bjdong_cd,
        stages=payload.stages,
        include_excluded=payload.include_excluded,
        formats=payload.formats,
    )

    region_code = (
        payload.sigungu_cd
        if payload.bjdong_cd == "00000"
        else f"{payload.sigungu_cd}{payload.bjdong_cd}"
    )

    run = ReportRun(
        region_code=region_code,
        excel_path=str(result.excel_path) if result.excel_path else None,
        pdf_path=str(result.pdf_path) if result.pdf_path else None,
        total_count=result.target_count,
        new_count=0,
        stage_changed_count=0,
        diff_json=None,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return ReportRunItem.model_validate(run)


@router.get("/{report_id}/download")
def download_report(
    report_id: int,
    format: Literal["excel", "pdf"] = Query(...),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Download generated Excel (.xlsx) or PDF (.pdf) report file."""
    run = db.get(ReportRun, report_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Report run not found: {report_id}")

    file_path_str = run.excel_path if format == "excel" else run.pdf_path
    if not file_path_str:
        raise HTTPException(
            status_code=404,
            detail=f"Report run {report_id} has no {format} file",
        )

    file_path = Path(file_path_str)
    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Report file missing on disk: {file_path.name}",
        )

    media_type = EXCEL_MEDIA_TYPE if format == "excel" else PDF_MEDIA_TYPE
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name,
    )
