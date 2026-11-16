"""Excel and PDF report generation package for House-Telecom."""

from backend.report.excel import (
    REQUIRED_SHEETS,
    SHEET_EXCLUDED,
    SHEET_NEAR_COMPLETION,
    SHEET_SUMMARY,
    SHEET_TARGETS,
    generate_excel_report,
)
from backend.report.pdf import build_report_html, generate_pdf_report
from backend.report.service import (
    GeneratedReportResult,
    ReportDataset,
    fetch_report_dataset,
    generate_reports,
)

__all__ = [
    "GeneratedReportResult",
    "REQUIRED_SHEETS",
    "ReportDataset",
    "SHEET_EXCLUDED",
    "SHEET_NEAR_COMPLETION",
    "SHEET_SUMMARY",
    "SHEET_TARGETS",
    "build_report_html",
    "fetch_report_dataset",
    "generate_excel_report",
    "generate_pdf_report",
    "generate_reports",
]
