"""Exclusion service and shared SQLAlchemy query helpers."""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.enums import ExclusionStatus
from shared.models import Building, ExclusionHistory
from shared.schemas import ExclusionBulkResponse, ExclusionBulkRowResult

QueryT = TypeVar("QueryT")


class BuildingNotFoundError(LookupError):
    """Raised when a target building PK does not exist."""


class NotExcludedError(ValueError):
    """Raised when attempting to restore a building that is not currently excluded."""


class InvalidCsvError(ValueError):
    """Raised when uploaded CSV content cannot be decoded or parsed."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _active_exclusion_exists():
    return (
        select(ExclusionHistory.id)
        .where(
            ExclusionHistory.mgm_pmsrgst_pk == Building.mgm_pmsrgst_pk,
            ExclusionHistory.is_active.is_(True),
        )
        .exists()
    )


def apply_exclusion_filter(query: QueryT, include_excluded: bool = False) -> QueryT:
    """Filter out currently-excluded buildings unless include_excluded=True.

    Works with both SQLAlchemy 2.0 `select(...)` statements and legacy `Session.query(...)`.
    """
    if include_excluded:
        return query
    return query.where(~_active_exclusion_exists())  # type: ignore[attr-defined]


def apply_only_excluded_filter(query: QueryT) -> QueryT:
    """Filter a Building query to include only currently-excluded buildings."""
    return query.where(_active_exclusion_exists())  # type: ignore[attr-defined]


def _get_building_or_raise(db: Session, mgm_pmsrgst_pk: str) -> Building:
    building = db.get(Building, mgm_pmsrgst_pk)
    if building is None:
        raise BuildingNotFoundError(f"Building '{mgm_pmsrgst_pk}' not found")
    return building


def exclude_building(
    db: Session,
    mgm_pmsrgst_pk: str,
    actor: str,
    status: ExclusionStatus,
    reason: str | None = None,
    evidence: str | None = None,
    *,
    commit: bool = True,
) -> ExclusionHistory:
    """Exclude a building and record an active ExclusionHistory entry.

    If the building already has an active exclusion, it is superseded (marked inactive
    with restored_at/restored_by set to the new actor) so at most one active exclusion
    exists per building.
    """
    _get_building_or_raise(db, mgm_pmsrgst_pk)

    now = _utcnow()
    existing_actives = db.scalars(
        select(ExclusionHistory).where(
            ExclusionHistory.mgm_pmsrgst_pk == mgm_pmsrgst_pk,
            ExclusionHistory.is_active.is_(True),
        )
    ).all()
    for active in existing_actives:
        active.is_active = False
        active.restored_at = now
        active.restored_by = actor

    entry = ExclusionHistory(
        mgm_pmsrgst_pk=mgm_pmsrgst_pk,
        actor=actor,
        created_at=now,
        status=status,
        reason=reason,
        evidence=evidence,
        is_active=True,
    )
    db.add(entry)
    if commit:
        db.commit()
        db.refresh(entry)
    else:
        db.flush()
    return entry


def restore_building(
    db: Session,
    mgm_pmsrgst_pk: str,
    restored_by: str,
    *,
    commit: bool = True,
) -> ExclusionHistory:
    """Restore (undo) an excluded building, making it an active target again."""
    _get_building_or_raise(db, mgm_pmsrgst_pk)

    active_entries = list(
        db.scalars(
            select(ExclusionHistory)
            .where(
                ExclusionHistory.mgm_pmsrgst_pk == mgm_pmsrgst_pk,
                ExclusionHistory.is_active.is_(True),
            )
            .order_by(ExclusionHistory.created_at.desc(), ExclusionHistory.id.desc())
        ).all()
    )
    if not active_entries:
        raise NotExcludedError(f"Building '{mgm_pmsrgst_pk}' is not currently excluded")

    now = _utcnow()
    for entry in active_entries:
        entry.is_active = False
        entry.restored_at = now
        entry.restored_by = restored_by

    latest = active_entries[0]
    if commit:
        db.commit()
        db.refresh(latest)
    else:
        db.flush()
    return latest


def get_active_exclusion(db: Session, mgm_pmsrgst_pk: str) -> ExclusionHistory | None:
    """Return the active ExclusionHistory for a building, or None if not excluded."""
    return db.scalars(
        select(ExclusionHistory)
        .where(
            ExclusionHistory.mgm_pmsrgst_pk == mgm_pmsrgst_pk,
            ExclusionHistory.is_active.is_(True),
        )
        .order_by(ExclusionHistory.created_at.desc(), ExclusionHistory.id.desc())
    ).first()


def is_building_excluded(db: Session, mgm_pmsrgst_pk: str) -> bool:
    """Return True if the building currently has an active exclusion."""
    return get_active_exclusion(db, mgm_pmsrgst_pk) is not None


def get_active_exclusion_map(
    db: Session,
    pks: Sequence[str] | None = None,
) -> dict[str, ExclusionHistory]:
    """Return a mapping of mgm_pmsrgst_pk -> active ExclusionHistory."""
    stmt = select(ExclusionHistory).where(ExclusionHistory.is_active.is_(True))
    if pks is not None:
        if not pks:
            return {}
        stmt = stmt.where(ExclusionHistory.mgm_pmsrgst_pk.in_(list(pks)))
    stmt = stmt.order_by(ExclusionHistory.created_at.desc(), ExclusionHistory.id.desc())

    result: dict[str, ExclusionHistory] = {}
    for entry in db.scalars(stmt).all():
        result.setdefault(entry.mgm_pmsrgst_pk, entry)
    return result


def get_building_exclusion_history(
    db: Session,
    mgm_pmsrgst_pk: str,
) -> list[ExclusionHistory]:
    """Return all exclusion/restoration history entries for a building, newest first."""
    _get_building_or_raise(db, mgm_pmsrgst_pk)
    return list(
        db.scalars(
            select(ExclusionHistory)
            .where(ExclusionHistory.mgm_pmsrgst_pk == mgm_pmsrgst_pk)
            .order_by(ExclusionHistory.created_at.desc(), ExclusionHistory.id.desc())
        ).all()
    )


def list_exclusions(
    db: Session,
    status: ExclusionStatus | None = None,
    active_only: bool = True,
) -> list[ExclusionHistory]:
    """List exclusion records, optionally filtered by status and active_only."""
    stmt = select(ExclusionHistory)
    if active_only:
        stmt = stmt.where(ExclusionHistory.is_active.is_(True))
    if status is not None:
        stmt = stmt.where(ExclusionHistory.status == status)
    stmt = stmt.order_by(ExclusionHistory.created_at.desc(), ExclusionHistory.id.desc())
    return list(db.scalars(stmt).all())


# ---------------------------------------------------------------------------
# CSV bulk exclusion helpers
# ---------------------------------------------------------------------------

_PK_ALIASES = ("mgm_pmsrgst_pk", "관리허가대장pk", "인허가pk", "pk")
_ADDR_ALIASES = ("plat_plc", "대지위치", "주소", "address")
_NAME_ALIASES = ("bld_nm", "건물명", "단지명", "building_name")
_REASON_ALIASES = ("reason", "사유")
_EVIDENCE_ALIASES = ("evidence", "증빙", "메모")
_STATUS_ALIASES = ("status", "상태")


def _decode_csv(content: bytes | str) -> str:
    if isinstance(content, str):
        return content.lstrip("\ufeff")
    for encoding in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise InvalidCsvError("Unable to decode CSV content (expected UTF-8 or CP949/EUC-KR)")


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.split()).strip().lower()


def _extract_field(normalized_row: dict[str, str], aliases: tuple[str, ...]) -> str:
    for alias in aliases:
        val = normalized_row.get(alias.lower(), "").strip()
        if val:
            return val
    return ""


def _match_building_for_row(
    db: Session,
    pk: str,
    plat_plc: str,
    bld_nm: str,
) -> tuple[Building | None, str | None]:
    """Match a Building by PK first, then by address and/or building name.

    Returns (building, error_detail). If building is None and error_detail is None,
    no matching building was found.
    """
    if pk:
        return db.get(Building, pk), None

    if plat_plc and bld_nm:
        exact = db.scalars(
            select(Building).where(Building.plat_plc == plat_plc, Building.bld_nm == bld_nm)
        ).all()
        if len(exact) == 1:
            return exact[0], None
        if len(exact) > 1:
            return None, f"Ambiguous match ({len(exact)} buildings)"

    if plat_plc:
        exact_addr = db.scalars(select(Building).where(Building.plat_plc == plat_plc)).all()
        if len(exact_addr) == 1:
            return exact_addr[0], None
        if len(exact_addr) > 1 and bld_nm:
            norm_nm = _normalize_text(bld_nm)
            filtered = [b for b in exact_addr if _normalize_text(b.bld_nm) == norm_nm]
            if len(filtered) == 1:
                return filtered[0], None
            if len(filtered) > 1:
                return None, f"Ambiguous match ({len(filtered)} buildings)"
        elif len(exact_addr) > 1:
            return None, f"Ambiguous match ({len(exact_addr)} buildings)"

    if bld_nm and not plat_plc:
        exact_name = db.scalars(select(Building).where(Building.bld_nm == bld_nm)).all()
        if len(exact_name) == 1:
            return exact_name[0], None
        if len(exact_name) > 1:
            return None, f"Ambiguous match ({len(exact_name)} buildings)"

    # Fallback: whitespace/case-normalized in-memory check over candidate rows
    norm_addr = _normalize_text(plat_plc)
    norm_name = _normalize_text(bld_nm)
    candidates = db.scalars(select(Building)).all()
    matches: list[Building] = []
    for b in candidates:
        b_addr = _normalize_text(b.plat_plc)
        b_name = _normalize_text(b.bld_nm)
        if norm_addr and norm_name:
            if b_addr == norm_addr and b_name == norm_name:
                matches.append(b)
        elif norm_addr:
            if b_addr == norm_addr:
                matches.append(b)
        elif norm_name:
            if b_name == norm_name:
                matches.append(b)

    if len(matches) == 1:
        return matches[0], None
    if len(matches) > 1:
        return None, f"Ambiguous match ({len(matches)} buildings)"
    return None, None


def bulk_exclude_from_csv(
    db: Session,
    csv_content: bytes | str,
    actor: str,
    status: ExclusionStatus = ExclusionStatus.TELECOM_DONE_SYSTEM,
    reason: str | None = None,
) -> ExclusionBulkResponse:
    """Bulk exclude buildings from a CSV upload.

    Matches each row by `mgm_pmsrgst_pk` first, or by address (`plat_plc` / `대지위치`)
    and/or building name (`bld_nm` / `건물명`).
    """
    text = _decode_csv(csv_content)
    if not text.strip():
        raise InvalidCsvError("CSV content is empty")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise InvalidCsvError("CSV header row is missing")

    results: list[ExclusionBulkRowResult] = []
    excluded_count = 0
    not_found_count = 0
    error_count = 0

    for row_number, raw_row in enumerate(reader, start=1):
        normalized_row = {
            (k or "").strip().lower(): (v or "").strip()
            for k, v in raw_row.items()
            if k is not None
        }
        pk = _extract_field(normalized_row, _PK_ALIASES)
        plat_plc = _extract_field(normalized_row, _ADDR_ALIASES)
        bld_nm = _extract_field(normalized_row, _NAME_ALIASES)
        row_reason = _extract_field(normalized_row, _REASON_ALIASES) or reason
        row_evidence = _extract_field(normalized_row, _EVIDENCE_ALIASES) or None
        row_status_str = _extract_field(normalized_row, _STATUS_ALIASES)

        identifier = pk or (f"{plat_plc} / {bld_nm}".strip(" /"))
        if not identifier:
            error_count += 1
            results.append(
                ExclusionBulkRowResult(
                    row_number=row_number,
                    identifier="",
                    matched_pk=None,
                    status="error",
                    detail="Missing identifier (mgm_pmsrgst_pk, plat_plc, or bld_nm)",
                )
            )
            continue

        row_status = status
        if row_status_str:
            try:
                row_status = ExclusionStatus(row_status_str)
            except ValueError:
                error_count += 1
                results.append(
                    ExclusionBulkRowResult(
                        row_number=row_number,
                        identifier=identifier,
                        matched_pk=None,
                        status="error",
                        detail=f"Invalid exclusion status '{row_status_str}'",
                    )
                )
                continue

        building, match_error = _match_building_for_row(db, pk=pk, plat_plc=plat_plc, bld_nm=bld_nm)
        if match_error:
            error_count += 1
            results.append(
                ExclusionBulkRowResult(
                    row_number=row_number,
                    identifier=identifier,
                    matched_pk=None,
                    status="error",
                    detail=match_error,
                )
            )
            continue

        if building is None:
            not_found_count += 1
            results.append(
                ExclusionBulkRowResult(
                    row_number=row_number,
                    identifier=identifier,
                    matched_pk=None,
                    status="not_found",
                    detail="No matching building found",
                )
            )
            continue

        exclude_building(
            db=db,
            mgm_pmsrgst_pk=building.mgm_pmsrgst_pk,
            actor=actor,
            status=row_status,
            reason=row_reason,
            evidence=row_evidence,
            commit=False,
        )
        excluded_count += 1
        results.append(
            ExclusionBulkRowResult(
                row_number=row_number,
                identifier=identifier,
                matched_pk=building.mgm_pmsrgst_pk,
                status="excluded",
                detail=None,
            )
        )

    db.commit()

    return ExclusionBulkResponse(
        total_rows=len(results),
        excluded_count=excluded_count,
        not_found_count=not_found_count,
        error_count=error_count,
        results=results,
    )
