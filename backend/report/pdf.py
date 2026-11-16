"""PDF report generator (WeasyPrint with PyMuPDF Story fallback on Windows)."""

from __future__ import annotations

import html
import math
from datetime import date
from pathlib import Path
from typing import Any, Sequence

from shared.enums import BuildingStage

STAGE_HEX: dict[BuildingStage, str] = {
    BuildingStage.PERMITTED: "#64748B",
    BuildingStage.START_SCHEDULED: "#CA8A04",
    BuildingStage.UNDER_CONSTRUCTION: "#2563EB",
    BuildingStage.NEAR_COMPLETION: "#DC2626",
    BuildingStage.USE_APPROVED: "#16A34A",
}

_FONT_CANDIDATES_STATIC = [
    Path("C:/Windows/Fonts/NotoSansKR-Regular.ttf"),
    Path("C:/Windows/Fonts/malgun.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansKR-Regular.ttf"),
]

_FONT_CANDIDATES_ALL = [
    Path("C:/Windows/Fonts/NotoSansKR-VF.ttf"),
    *_FONT_CANDIDATES_STATIC,
]


def _resolve_korean_font_path(static_only: bool = False) -> Path | None:
    candidates = _FONT_CANDIDATES_STATIC if static_only else _FONT_CANDIDATES_ALL
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _stage_enum(value: Any) -> BuildingStage:
    if isinstance(value, BuildingStage):
        return value
    return BuildingStage(str(value))


def _build_bar_chart_svg(stage_counts: list[tuple[BuildingStage, int]]) -> str:
    width = 360
    height = 175
    max_val = max((c for _, c in stage_counts), default=1) or 1
    bar_area_w = 180
    rows_svg: list[str] = []

    for idx, (stage, count) in enumerate(stage_counts):
        y = 14 + idx * 31
        bar_w = int((count / max_val) * bar_area_w) if count > 0 else 2
        color = STAGE_HEX[stage]
        label = html.escape(stage.label_ko)
        rows_svg.append(
            f'<text x="4" y="{y + 14}" font-size="10" fill="#1E293B">{label}</text>'
            f'<rect x="78" y="{y}" width="{bar_w}" height="18" rx="3" fill="{color}"/>'
            f'<text x="{84 + bar_w}" y="{y + 13}" font-size="10" fill="#334155">{count}건</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        + "".join(rows_svg)
        + "</svg>"
    )


def _build_donut_chart_svg(stage_counts: list[tuple[BuildingStage, int]]) -> str:
    total = sum(c for _, c in stage_counts)
    cx, cy, r = 72, 85, 52
    circumference = 2 * math.pi * r
    segments: list[str] = []
    legend: list[str] = []

    if total == 0:
        segments.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#E2E8F0" stroke-width="20"/>'
        )
    else:
        offset = 0.0
        for stage, count in stage_counts:
            if count <= 0:
                continue
            frac = count / total
            dash = frac * circumference
            color = STAGE_HEX[stage]
            segments.append(
                f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" '
                f'stroke-width="20" stroke-dasharray="{dash:.2f} {circumference:.2f}" '
                f'stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 {cx} {cy})"/>'
            )
            offset += dash

    for idx, (stage, count) in enumerate(stage_counts):
        ly = 24 + idx * 26
        pct = (count / total * 100.0) if total > 0 else 0.0
        color = STAGE_HEX[stage]
        legend.append(
            f'<rect x="155" y="{ly - 9}" width="10" height="10" rx="2" fill="{color}"/>'
            f'<text x="171" y="{ly}" font-size="10" fill="#1E293B">'
            f"{html.escape(stage.label_ko)}: {count}건 ({pct:.1f}%)</text>"
        )

    center_text = (
        f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" font-size="12" '
        f'font-weight="bold" fill="#0F172A">총 {total}건</text>'
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="330" height="175" viewBox="0 0 330 175">'
        + "".join(segments)
        + center_text
        + "".join(legend)
        + "</svg>"
    )


def build_report_html(
    buildings: Sequence[Any],
    excluded_rows: Sequence[dict[str, Any]],
    region_name: str = "",
    reference_date: str | None = None,
    relative_font_src: bool = False,
) -> str:
    """Render HTML document with Noto Sans KR, SVG charts, and priority target table."""
    ref_date = reference_date or date.today().isoformat()
    sorted_buildings = sorted(
        buildings,
        key=lambda b: float(getattr(b, "priority_score") or 0.0),
        reverse=True,
    )
    total_count = len(sorted_buildings)
    near_count = sum(
        1 for b in sorted_buildings if _stage_enum(getattr(b, "stage")) == BuildingStage.NEAR_COMPLETION
    )
    excluded_count = len(excluded_rows)
    avg_score = (
        round(sum(float(getattr(b, "priority_score") or 0.0) for b in sorted_buildings) / total_count, 1)
        if total_count > 0
        else 0.0
    )

    stage_counts: list[tuple[BuildingStage, int]] = [
        (
            stage,
            sum(1 for b in sorted_buildings if _stage_enum(getattr(b, "stage")) == stage),
        )
        for stage in BuildingStage
    ]

    font_path = _resolve_korean_font_path(static_only=relative_font_src)
    font_face_css = ""
    if font_path is not None:
        font_src = font_path.name if relative_font_src else font_path.as_uri()
        font_face_css = (
            "@font-face {"
            '  font-family: "Noto Sans KR";'
            f'  src: url("{font_src}");'
            "}"
        )

    bar_svg = _build_bar_chart_svg(stage_counts)
    donut_svg = _build_donut_chart_svg(stage_counts)

    rows_html: list[str] = []
    for idx, b in enumerate(sorted_buildings, start=1):
        stage = _stage_enum(getattr(b, "stage"))
        color = STAGE_HEX[stage]
        bld_nm = html.escape(str(getattr(b, "bld_nm") or "-"))
        plat_plc = html.escape(str(getattr(b, "plat_plc") or "-"))
        purps = html.escape(str(getattr(b, "main_purps_cd_nm") or "-"))
        hhld = int(getattr(b, "hhld_cnt") or 0)
        area = float(getattr(b, "tot_area") or 0.0)
        score = float(getattr(b, "priority_score") or 0.0)
        rows_html.append(
            "<tr>"
            f'<td class="center">{idx}</td>'
            f"<td>{bld_nm}</td>"
            f"<td>{plat_plc}</td>"
            f"<td>{purps}</td>"
            f'<td class="right">{hhld:,}</td>'
            f'<td class="right">{area:,.1f}</td>'
            f'<td class="center"><span class="badge" style="background:{color};">'
            f"{html.escape(stage.label_ko)}</span></td>"
            f'<td class="right"><strong>{score:.1f}</strong></td>'
            "</tr>"
        )

    if not rows_html:
        rows_html.append(
            '<tr><td colspan="8" class="center">표시할 미확인 대상 건물이 없습니다.</td></tr>'
        )

    region_esc = html.escape(region_name or "전체 지역")
    ref_esc = html.escape(ref_date)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<title>신축 통신공사 사전파악 리포트</title>
<style>
{font_face_css}
@page {{
  size: A4;
  margin: 16mm 14mm;
}}
body {{
  font-family: "Noto Sans KR", "Malgun Gothic", sans-serif;
  color: #0F172A;
  font-size: 9.5pt;
  line-height: 1.45;
  margin: 0;
}}
.header {{
  border-bottom: 2px solid #1E293B;
  padding-bottom: 10px;
  margin-bottom: 14px;
}}
.header h1 {{
  font-size: 16pt;
  margin: 0 0 4px 0;
  color: #0F172A;
}}
.meta {{
  font-size: 9pt;
  color: #475569;
}}
.kpi-table {{
  width: 100%;
  border-collapse: separate;
  border-spacing: 8px 0;
  margin: 10px -8px 14px -8px;
}}
.kpi-card {{
  border: 1px solid #CBD5E1;
  border-radius: 6px;
  padding: 8px 10px;
  background: #F8FAFC;
  width: 25%;
}}
.kpi-label {{
  font-size: 8pt;
  color: #475569;
}}
.kpi-value {{
  font-size: 13pt;
  font-weight: bold;
  color: #0F172A;
  margin-top: 2px;
}}
.section-title {{
  font-size: 11.5pt;
  font-weight: bold;
  color: #1E293B;
  margin: 14px 0 8px 0;
  border-left: 3px solid #2563EB;
  padding-left: 8px;
}}
.charts-table {{
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 12px;
}}
.charts-table td {{
  width: 50%;
  vertical-align: top;
  border: 1px solid #E2E8F0;
  padding: 8px;
  background: #FFFFFF;
}}
table.data {{
  width: 100%;
  border-collapse: collapse;
  font-size: 8.5pt;
}}
table.data th {{
  background: #1E293B;
  color: #FFFFFF;
  padding: 6px 5px;
  text-align: center;
  border: 1px solid #1E293B;
}}
table.data td {{
  padding: 5px;
  border: 1px solid #CBD5E1;
  vertical-align: middle;
}}
.center {{ text-align: center; }}
.right {{ text-align: right; }}
.badge {{
  display: inline-block;
  color: #FFFFFF;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 7.5pt;
  font-weight: bold;
}}
</style>
</head>
<body>
  <div class="header">
    <h1>신축 통신공사 사전파악 리포트</h1>
    <div class="meta">대상 지역: {region_esc} | 기준일: {ref_esc} | 총 대상 건수: {total_count}건 (준공임박 {near_count}건, 제외 {excluded_count}건)</div>
  </div>

  <table class="kpi-table">
    <tr>
      <td class="kpi-card"><div class="kpi-label">미확인 대상 건수</div><div class="kpi-value">{total_count}건</div></td>
      <td class="kpi-card"><div class="kpi-label">준공임박 건수</div><div class="kpi-value">{near_count}건</div></td>
      <td class="kpi-card"><div class="kpi-label">제외 목록 건수</div><div class="kpi-value">{excluded_count}건</div></td>
      <td class="kpi-card"><div class="kpi-label">평균 우선순위</div><div class="kpi-value">{avg_score:.1f}점</div></td>
    </tr>
  </table>

  <div class="section-title">진행단계별 요약 차트</div>
  <table class="charts-table">
    <tr>
      <td>{bar_svg}</td>
      <td>{donut_svg}</td>
    </tr>
  </table>

  <div class="section-title">우선순위 대상 건물 목록 (총 {total_count}건)</div>
  <table class="data">
    <thead>
      <tr>
        <th style="width:5%;">순번</th>
        <th style="width:18%;">건물명</th>
        <th style="width:26%;">대지위치</th>
        <th style="width:14%;">주용도</th>
        <th style="width:8%;">세대수</th>
        <th style="width:10%;">연면적(㎡)</th>
        <th style="width:11%;">진행단계</th>
        <th style="width:8%;">점수</th>
      </tr>
    </thead>
    <tbody>
      {"".join(rows_html)}
    </tbody>
  </table>
</body>
</html>
"""


def _render_with_weasyprint(html_str: str, output_path: Path) -> None:
    import weasyprint  # type: ignore

    weasyprint.HTML(string=html_str).write_pdf(str(output_path))


def _render_with_pymupdf(html_str: str, output_path: Path) -> None:
    import fitz  # PyMuPDF

    font_path = _resolve_korean_font_path(static_only=True)
    archive = fitz.Archive(str(font_path.parent)) if font_path is not None else None
    story = fitz.Story(html=html_str, archive=archive)
    writer = fitz.DocumentWriter(str(output_path))
    mediabox = fitz.paper_rect("a4")
    where = mediabox + (36, 36, -36, -36)

    more = True
    while more:
        dev = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(dev, None)
        writer.end_page()
    writer.close()


def generate_pdf_report(
    buildings: Sequence[Any],
    excluded_rows: Sequence[dict[str, Any]],
    output_path: str | Path,
    region_name: str = "",
    reference_date: str | None = None,
) -> Path:
    """Generate a PDF report from HTML+SVG template using WeasyPrint or PyMuPDF fallback."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    html_str = build_report_html(
        buildings=buildings,
        excluded_rows=excluded_rows,
        region_name=region_name,
        reference_date=reference_date,
        relative_font_src=False,
    )

    try:
        _render_with_weasyprint(html_str, out)
    except (ImportError, OSError):
        pymupdf_html = build_report_html(
            buildings=buildings,
            excluded_rows=excluded_rows,
            region_name=region_name,
            reference_date=reference_date,
            relative_font_src=True,
        )
        _render_with_pymupdf(pymupdf_html, out)

    return out
