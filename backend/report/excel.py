"""Excel report generator using openpyxl for House-Telecom."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Sequence

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from backend.stage import estimate_completion_month
from shared.enums import BuildingStage, ExclusionStatus

SHEET_SUMMARY = "요약"
SHEET_TARGETS = "미확인 대상"
SHEET_NEAR_COMPLETION = "준공임박"
SHEET_EXCLUDED = "제외 목록"

REQUIRED_SHEETS = (
    SHEET_SUMMARY,
    SHEET_TARGETS,
    SHEET_NEAR_COMPLETION,
    SHEET_EXCLUDED,
)

TARGET_HEADERS = [
    "관리허가대장PK",
    "시군구코드",
    "법정동코드",
    "대지위치",
    "건물명",
    "주용도",
    "연면적(㎡)",
    "세대수",
    "동수",
    "건축허가일",
    "착공예정일",
    "실제착공일",
    "사용승인일",
    "예상준공월",
    "진행단계",
    "우선순위점수",
]

TARGET_COL_WIDTHS = [24, 12, 12, 34, 24, 18, 15, 10, 10, 13, 13, 13, 13, 13, 14, 15]

EXCLUDED_HEADERS = [
    "관리허가대장PK",
    "건물명",
    "대지위치",
    "주용도",
    "진행단계",
    "제외유형",
    "제외사유",
    "증빙메모/경로",
    "처리자",
    "처리일시",
]

EXCLUDED_COL_WIDTHS = [24, 24, 34, 18, 14, 20, 28, 28, 14, 20]

STAGE_COLORS: dict[BuildingStage, tuple[str, str]] = {
    BuildingStage.PERMITTED: ("F1F5F9", "334155"),
    BuildingStage.START_SCHEDULED: ("FEF9C3", "854D0E"),
    BuildingStage.UNDER_CONSTRUCTION: ("DBEAFE", "1E40AF"),
    BuildingStage.NEAR_COMPLETION: ("FEE2E2", "991B1B"),
    BuildingStage.USE_APPROVED: ("DCFCE7", "166534"),
}

_HEADER_FILL = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
_HEADER_FONT = Font(name="맑은 고딕", size=10, bold=True, color="FFFFFF")
_TITLE_FONT = Font(name="맑은 고딕", size=15, bold=True, color="0F172A")
_SUBTITLE_FONT = Font(name="맑은 고딕", size=10, color="475569")
_SECTION_FONT = Font(name="맑은 고딕", size=11, bold=True, color="0F172A")
_BODY_FONT = Font(name="맑은 고딕", size=10, color="1E293B")
_THIN_BORDER = Border(
    left=Side(style="thin", color="CBD5E1"),
    right=Side(style="thin", color="CBD5E1"),
    top=Side(style="thin", color="CBD5E1"),
    bottom=Side(style="thin", color="CBD5E1"),
)


def _stage_enum(value: Any) -> BuildingStage:
    if isinstance(value, BuildingStage):
        return value
    return BuildingStage(str(value))


def _exclusion_label(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, ExclusionStatus):
        return value.label_ko
    try:
        return ExclusionStatus(str(value)).label_ko
    except ValueError:
        return str(value)


def _fmt_dt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    return str(value)


def _style_header_row(ws: Worksheet, num_cols: int, row_idx: int = 1) -> None:
    ws.row_dimensions[row_idx].height = 24
    for col_idx in range(1, num_cols + 1):
        cell = ws.cell(row=row_idx, column=col_idx)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = _THIN_BORDER


def _apply_stage_conditional_formatting(ws: Worksheet, stage_col_letter: str, max_row: int) -> None:
    if max_row < 2:
        return
    cell_range = f"{stage_col_letter}2:{stage_col_letter}{max_row}"
    for stage, (bg_hex, fg_hex) in STAGE_COLORS.items():
        rule = CellIsRule(
            operator="equal",
            formula=[f'"{stage.label_ko}"'],
            stopIfTrue=True,
            fill=PatternFill(start_color=bg_hex, end_color=bg_hex, fill_type="solid"),
            font=Font(name="맑은 고딕", size=10, bold=True, color=fg_hex),
        )
        ws.conditional_formatting.add(cell_range, rule)


def _write_building_sheet(ws: Worksheet, buildings: Sequence[Any]) -> None:
    ws.append(TARGET_HEADERS)
    _style_header_row(ws, len(TARGET_HEADERS), row_idx=1)

    for b in buildings:
        stage = _stage_enum(getattr(b, "stage"))
        expected_month = estimate_completion_month(
            real_stcns_day=getattr(b, "real_stcns_day", None),
            stcns_sched_day=getattr(b, "stcns_sched_day", None),
            use_apr_day=getattr(b, "use_apr_day", None),
            tot_area=getattr(b, "tot_area", None),
        )
        ws.append(
            [
                getattr(b, "mgm_pmsrgst_pk", "") or "",
                getattr(b, "sigungu_cd", "") or "",
                getattr(b, "bjdong_cd", "") or "",
                getattr(b, "plat_plc", "") or "",
                getattr(b, "bld_nm", "") or "",
                getattr(b, "main_purps_cd_nm", "") or "",
                float(getattr(b, "tot_area") or 0.0),
                int(getattr(b, "hhld_cnt") or 0),
                int(getattr(b, "dong_cnt") or 0),
                getattr(b, "arch_pms_day", "") or "",
                getattr(b, "stcns_sched_day", "") or "",
                getattr(b, "real_stcns_day", "") or "",
                getattr(b, "use_apr_day", "") or "",
                expected_month or "-",
                stage.label_ko,
                round(float(getattr(b, "priority_score") or 0.0), 2),
            ]
        )

    max_row = max(ws.max_row, 1)
    for row_idx in range(2, max_row + 1):
        ws.row_dimensions[row_idx].height = 20
        for col_idx in range(1, len(TARGET_HEADERS) + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.font = _BODY_FONT
            cell.border = _THIN_BORDER
            if col_idx in (7, 16):
                cell.number_format = "#,##0.00"
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif col_idx in (8, 9):
                cell.number_format = "#,##0"
                cell.alignment = Alignment(horizontal="right", vertical="center")
            elif col_idx in (2, 3, 10, 11, 12, 13, 14, 15):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    for idx, width in enumerate(TARGET_COL_WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(TARGET_HEADERS))}{max_row}"
    _apply_stage_conditional_formatting(ws, "O", max_row)


def _write_excluded_sheet(ws: Worksheet, excluded_rows: Sequence[dict[str, Any]]) -> None:
    ws.append(EXCLUDED_HEADERS)
    _style_header_row(ws, len(EXCLUDED_HEADERS), row_idx=1)

    for item in excluded_rows:
        stage_val = item.get("stage")
        stage_label = _stage_enum(stage_val).label_ko if stage_val is not None else ""
        ws.append(
            [
                item.get("mgm_pmsrgst_pk", "") or "",
                item.get("bld_nm", "") or "",
                item.get("plat_plc", "") or "",
                item.get("main_purps_cd_nm", "") or "",
                stage_label,
                _exclusion_label(item.get("status")),
                item.get("reason", "") or "",
                item.get("evidence", "") or "",
                item.get("actor", "") or "",
                _fmt_dt(item.get("created_at")),
            ]
        )

    max_row = max(ws.max_row, 1)
    for row_idx in range(2, max_row + 1):
        ws.row_dimensions[row_idx].height = 20
        for col_idx in range(1, len(EXCLUDED_HEADERS) + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.font = _BODY_FONT
            cell.border = _THIN_BORDER
            cell.alignment = Alignment(
                horizontal="center" if col_idx in (5, 6, 9, 10) else "left",
                vertical="center",
            )

    for idx, width in enumerate(EXCLUDED_COL_WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(EXCLUDED_HEADERS))}{max_row}"


def _write_summary_sheet(
    ws: Worksheet,
    buildings: Sequence[Any],
    near_completion: Sequence[Any],
    excluded_rows: Sequence[dict[str, Any]],
    region_name: str,
    reference_date: str,
) -> None:
    ws["A1"] = "신축 통신공사 사전파악 리포트 요약"
    ws["A1"].font = _TITLE_FONT
    ws["A2"] = f"대상 지역: {region_name or '전체'} | 기준일: {reference_date}"
    ws["A2"].font = _SUBTITLE_FONT

    kpi_headers = ["항목", "건수 / 수치"]
    ws["A4"], ws["B4"] = kpi_headers[0], kpi_headers[1]
    _style_header_row(ws, 2, row_idx=4)

    avg_score = (
        round(sum(float(getattr(b, "priority_score") or 0.0) for b in buildings) / len(buildings), 2)
        if buildings
        else 0.0
    )
    kpis = [
        ("미확인 대상 건물 수", len(buildings)),
        ("준공임박 대상 건수", len(near_completion)),
        ("제외 목록 건수", len(excluded_rows)),
        ("평균 우선순위 점수", avg_score),
    ]
    for offset, (label, val) in enumerate(kpis, start=5):
        ws.cell(row=offset, column=1, value=label).font = _BODY_FONT
        c = ws.cell(row=offset, column=2, value=val)
        c.font = _BODY_FONT
        c.number_format = "#,##0.00" if isinstance(val, float) else "#,##0"
        c.alignment = Alignment(horizontal="right", vertical="center")
        ws.cell(row=offset, column=1).border = _THIN_BORDER
        c.border = _THIN_BORDER

    ws["A10"] = "진행단계별 현황"
    ws["A10"].font = _SECTION_FONT

    stage_headers = ["진행단계", "건수", "비중(%)", "평균 우선순위 점수"]
    for idx, h in enumerate(stage_headers, start=1):
        ws.cell(row=11, column=idx, value=h)
    _style_header_row(ws, len(stage_headers), row_idx=11)

    total = len(buildings)
    for idx, stage in enumerate(BuildingStage, start=12):
        stage_items = [b for b in buildings if _stage_enum(getattr(b, "stage")) == stage]
        cnt = len(stage_items)
        ratio = round((cnt / total * 100.0), 1) if total > 0 else 0.0
        stage_avg = (
            round(sum(float(getattr(b, "priority_score") or 0.0) for b in stage_items) / cnt, 2)
            if cnt > 0
            else 0.0
        )
        row_vals = [stage.label_ko, cnt, ratio, stage_avg]
        for col_idx, val in enumerate(row_vals, start=1):
            cell = ws.cell(row=idx, column=col_idx, value=val)
            cell.font = _BODY_FONT
            cell.border = _THIN_BORDER
            if col_idx == 1:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif col_idx == 2:
                cell.number_format = "#,##0"
                cell.alignment = Alignment(horizontal="right", vertical="center")
            else:
                cell.number_format = "#,##0.00" if col_idx == 4 else "0.0"
                cell.alignment = Alignment(horizontal="right", vertical="center")

    _apply_stage_conditional_formatting(ws, "A", 11 + len(BuildingStage))
    for col_idx, width in enumerate([26, 16, 14, 22], start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width


def generate_excel_report(
    buildings: Sequence[Any],
    excluded_rows: Sequence[dict[str, Any]],
    output_path: str | Path,
    region_name: str = "",
    reference_date: str | None = None,
) -> Path:
    """Generate a multi-sheet Excel report (.xlsx) and return the written path."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    ref_date = reference_date or date.today().isoformat()

    sorted_buildings = sorted(
        buildings,
        key=lambda b: float(getattr(b, "priority_score") or 0.0),
        reverse=True,
    )
    near_completion = [
        b
        for b in sorted_buildings
        if _stage_enum(getattr(b, "stage")) == BuildingStage.NEAR_COMPLETION
    ]

    wb = Workbook()
    ws_summary = wb.active
    ws_summary.title = SHEET_SUMMARY
    _write_summary_sheet(
        ws_summary,
        sorted_buildings,
        near_completion,
        excluded_rows,
        region_name=region_name,
        reference_date=ref_date,
    )

    ws_targets = wb.create_sheet(title=SHEET_TARGETS)
    _write_building_sheet(ws_targets, sorted_buildings)

    ws_near = wb.create_sheet(title=SHEET_NEAR_COMPLETION)
    _write_building_sheet(ws_near, near_completion)

    ws_excluded = wb.create_sheet(title=SHEET_EXCLUDED)
    _write_excluded_sheet(ws_excluded, excluded_rows)

    wb.save(out)
    return out
