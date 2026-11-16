"""CLI entrypoint for manually running the weekly report pipeline."""

from __future__ import annotations

import argparse
import json
import sys

from backend.jobs.pipeline import run_all_active_regions, run_weekly_pipeline
from shared.database import init_db


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run House-Telecom weekly report pipeline")
    parser.add_argument(
        "--region",
        help="5-digit sigungu_cd or 10-digit region_code (omit to run all active InterestRegions)",
    )
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Use local fixture data instead of calling the live data.go.kr API",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to write generated Excel and PDF reports",
    )
    parser.add_argument(
        "--include-excluded",
        action="store_true",
        help="Include excluded buildings in the report",
    )
    args = parser.parse_args(argv)

    init_db()
    if args.region:
        runs = [
            run_weekly_pipeline(
                args.region,
                use_fixture=args.fixture,
                output_dir=args.output_dir,
                include_excluded=args.include_excluded,
            )
        ]
    else:
        runs = run_all_active_regions(
            use_fixture=args.fixture,
            output_dir=args.output_dir,
            include_excluded=args.include_excluded,
        )

    summary = [
        {
            "id": r.id,
            "region_code": r.region_code,
            "total_count": r.total_count,
            "new_count": r.new_count,
            "stage_changed_count": r.stage_changed_count,
            "excel_path": r.excel_path,
            "pdf_path": r.pdf_path,
        }
        for r in runs
    ]
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
