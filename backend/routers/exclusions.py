"""Exclusions & restoration API router."""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from backend.exclusion import (
    BuildingNotFoundError,
    InvalidCsvError,
    NotExcludedError,
    bulk_exclude_from_csv,
    exclude_building,
    get_building_exclusion_history,
    list_exclusions,
    restore_building,
)
from shared.database import get_db
from shared.enums import ExclusionStatus
from shared.schemas import (
    ExclusionBulkResponse,
    ExclusionCreateRequest,
    ExclusionHistoryItem,
    ExclusionListResponse,
    ExclusionRestoreRequest,
)

router = APIRouter(prefix="/api/exclusions", tags=["exclusions"])


@router.get("", response_model=ExclusionListResponse)
def get_exclusions(
    status: Optional[ExclusionStatus] = Query(default=None),
    active_only: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> ExclusionListResponse:
    """List exclusion records filtered by status and active flag."""
    rows = list_exclusions(db, status=status, active_only=active_only)
    items = [ExclusionHistoryItem.model_validate(r) for r in rows]
    return ExclusionListResponse(items=items, total=len(items))


@router.post("", response_model=ExclusionHistoryItem, status_code=201)
def create_exclusion(
    payload: ExclusionCreateRequest,
    db: Session = Depends(get_db),
) -> ExclusionHistoryItem:
    """Exclude a building from active telecom sales targets."""
    try:
        entry = exclude_building(
            db,
            mgm_pmsrgst_pk=payload.mgm_pmsrgst_pk,
            actor=payload.actor,
            status=payload.status,
            reason=payload.reason,
            evidence=payload.evidence,
        )
    except BuildingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ExclusionHistoryItem.model_validate(entry)


@router.post("/bulk-csv", response_model=ExclusionBulkResponse)
async def bulk_exclude_csv(
    file: UploadFile = File(...),
    actor: str = Form(..., min_length=1, max_length=100),
    status: ExclusionStatus = Form(default=ExclusionStatus.TELECOM_DONE_SYSTEM),
    reason: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
) -> ExclusionBulkResponse:
    """Bulk exclude buildings from an uploaded CSV file."""
    content = await file.read()
    try:
        return bulk_exclude_from_csv(
            db,
            csv_content=content,
            actor=actor,
            status=status,
            reason=reason,
        )
    except InvalidCsvError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{mgm_pmsrgst_pk}/restore", response_model=ExclusionHistoryItem)
def restore_excluded_building(
    mgm_pmsrgst_pk: str,
    payload: ExclusionRestoreRequest,
    db: Session = Depends(get_db),
) -> ExclusionHistoryItem:
    """Restore (undo) an excluded building."""
    try:
        entry = restore_building(
            db,
            mgm_pmsrgst_pk=mgm_pmsrgst_pk,
            restored_by=payload.restored_by,
        )
    except BuildingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NotExcludedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ExclusionHistoryItem.model_validate(entry)


@router.get("/{mgm_pmsrgst_pk}/history", response_model=ExclusionListResponse)
def get_exclusion_history(
    mgm_pmsrgst_pk: str,
    db: Session = Depends(get_db),
) -> ExclusionListResponse:
    """Return full exclusion/restoration history for a specific building."""
    try:
        rows = get_building_exclusion_history(db, mgm_pmsrgst_pk)
    except BuildingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    items = [ExclusionHistoryItem.model_validate(r) for r in rows]
    return ExclusionListResponse(items=items, total=len(items))
