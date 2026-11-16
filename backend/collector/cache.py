"""Monthly-aware raw API response cache."""

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional


class RawResponseCache:
    """File-based JSON cache partitioned by YYYY-MM for monthly data refresh awareness."""

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        self.cache_dir = cache_dir or (Path(__file__).resolve().parent / ".cache")

    @staticmethod
    def current_month_bucket(reference_date: Optional[date] = None) -> str:
        ref = reference_date or datetime.now(timezone.utc).date()
        return ref.strftime("%Y-%m")

    def _key_path(
        self,
        operation: str,
        sigungu_cd: str,
        bjdong_cd: str,
        page_no: int,
        num_of_rows: int,
        month_bucket: Optional[str] = None,
    ) -> Path:
        bucket = month_bucket or self.current_month_bucket()
        filename = f"{operation}_{sigungu_cd}_{bjdong_cd}_p{page_no}_n{num_of_rows}.json"
        return self.cache_dir / bucket / filename

    def get(
        self,
        operation: str,
        sigungu_cd: str,
        bjdong_cd: str,
        page_no: int,
        num_of_rows: int,
        month_bucket: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        path = self._key_path(operation, sigungu_cd, bjdong_cd, page_no, num_of_rows, month_bucket)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def set(
        self,
        operation: str,
        sigungu_cd: str,
        bjdong_cd: str,
        page_no: int,
        num_of_rows: int,
        payload: dict[str, Any],
        month_bucket: Optional[str] = None,
    ) -> Path:
        path = self._key_path(operation, sigungu_cd, bjdong_cd, page_no, num_of_rows, month_bucket)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return path
