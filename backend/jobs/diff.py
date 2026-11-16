"""Diff computation and region code helpers for weekly report runs."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from shared.models import Building, ReportRun


def parse_region_code(region_code: str) -> tuple[str, str]:
    """Parse a 5-digit sigungu code or 10-digit law-dong code into (sigungu_cd, bjdong_cd)."""
    cleaned = region_code.strip()
    if len(cleaned) == 5 and cleaned.isdigit():
        return cleaned, "00000"
    if len(cleaned) == 10 and cleaned.isdigit():
        return cleaned[:5], cleaned[5:]
    raise ValueError(
        f"Invalid region_code {region_code!r}: expected 5-digit sigungu_cd or 10-digit code."
    )


def format_region_code(sigungu_cd: str, bjdong_cd: str = "00000") -> str:
    """Normalize sigungu_cd and bjdong_cd into a 10-digit region_code."""
    return f"{sigungu_cd.strip()}{(bjdong_cd or '00000').strip()}"


def _stage_value(stage: Any) -> str:
    return stage.value if hasattr(stage, "value") else str(stage)


def compute_building_diff(
    buildings: Sequence[Building],
    previous_run: ReportRun | None,
) -> dict[str, Any]:
    """Compute new and stage-changed buildings compared to the previous ReportRun."""
    prev_snapshot: dict[str, dict[str, Any]] | None = None
    if previous_run is not None and isinstance(previous_run.diff_json, dict):
        raw_snapshot = previous_run.diff_json.get("snapshot")
        if isinstance(raw_snapshot, dict):
            prev_snapshot = raw_snapshot

    new_buildings: list[dict[str, Any]] = []
    stage_changed_buildings: list[dict[str, Any]] = []
    snapshot: dict[str, dict[str, Any]] = {}

    for b in buildings:
        stage_val = _stage_value(b.stage)
        entry = {
            "mgm_pmsrgst_pk": b.mgm_pmsrgst_pk,
            "bld_nm": b.bld_nm,
            "plat_plc": b.plat_plc,
            "stage": stage_val,
            "priority_score": float(b.priority_score),
        }
        snapshot[b.mgm_pmsrgst_pk] = entry

        if prev_snapshot is None or b.mgm_pmsrgst_pk not in prev_snapshot:
            new_buildings.append(entry)
        else:
            prev_stage = prev_snapshot[b.mgm_pmsrgst_pk].get("stage")
            if prev_stage != stage_val:
                stage_changed_buildings.append(
                    {
                        "mgm_pmsrgst_pk": b.mgm_pmsrgst_pk,
                        "bld_nm": b.bld_nm,
                        "plat_plc": b.plat_plc,
                        "old_stage": prev_stage,
                        "new_stage": stage_val,
                        "priority_score": float(b.priority_score),
                    }
                )

    return {
        "new_buildings": new_buildings,
        "stage_changed_buildings": stage_changed_buildings,
        "snapshot": snapshot,
    }
