"""Regions hierarchy & 법정동코드 API router."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.region.service import (
    list_emd,
    list_sido,
    list_sigungu,
    to_api_params,
)
from shared.database import get_db
from shared.schemas import RegionApiParams, RegionItem, RegionListResponse

router = APIRouter(prefix="/api/regions", tags=["regions"])


@router.get("/sido", response_model=RegionListResponse)
def get_sido_list(db: Session = Depends(get_db)) -> RegionListResponse:
    """Return all active 시/도 regions."""
    rows = list_sido(db)
    items = [RegionItem.model_validate(r) for r in rows]
    return RegionListResponse(items=items, total=len(items))


@router.get("/sigungu", response_model=RegionListResponse)
def get_sigungu_list(
    sido_cd: str = Query(..., min_length=2, max_length=2, description="시도코드 2자리"),
    db: Session = Depends(get_db),
) -> RegionListResponse:
    """Return active 시/군/구 regions for the given sido_cd."""
    rows = list_sigungu(db, sido_cd)
    items = [RegionItem.model_validate(r) for r in rows]
    return RegionListResponse(items=items, total=len(items))


@router.get("/emd", response_model=RegionListResponse)
def get_emd_list(
    sigungu_cd: str = Query(..., min_length=5, max_length=5, description="시군구코드 5자리"),
    include_ri: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> RegionListResponse:
    """Return active 읍/면/동 regions for the given sigungu_cd."""
    rows = list_emd(db, sigungu_cd, include_ri=include_ri)
    items = [RegionItem.model_validate(r) for r in rows]
    return RegionListResponse(items=items, total=len(items))


@router.get("/api-params", response_model=RegionApiParams)
def get_region_api_params(
    code: str = Query(..., min_length=5, max_length=10, description="법정동코드 5자리 또는 10자리"),
) -> RegionApiParams:
    """Convert a 10-digit or 5-digit region code to 건축HUB API parameters."""
    try:
        return to_api_params(code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
