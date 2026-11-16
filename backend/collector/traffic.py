"""Daily API traffic counter backed by ApiTrafficLog."""

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.collector.exceptions import DailyQuotaExceededError
from shared.models import ApiTrafficLog


class TrafficLimiter:
    """Tracks and enforces the data.go.kr daily API call limit (default 10,000/day)."""

    def __init__(self, db: Session, daily_limit: int = 10000) -> None:
        self.db = db
        self.daily_limit = daily_limit

    def _get_or_create_log(self, target_date: Optional[date] = None) -> ApiTrafficLog:
        log_date = target_date or datetime.now(timezone.utc).date()
        stmt = select(ApiTrafficLog).where(ApiTrafficLog.log_date == log_date)
        log = self.db.execute(stmt).scalar_one_or_none()
        if log is None:
            log = ApiTrafficLog(
                log_date=log_date,
                request_count=0,
                daily_limit=self.daily_limit,
                last_called_at=None,
            )
            self.db.add(log)
            self.db.flush()
        return log

    def get_remaining_quota(self, target_date: Optional[date] = None) -> int:
        log = self._get_or_create_log(target_date)
        return max(0, log.daily_limit - log.request_count)

    def consume(self, count: int = 1, target_date: Optional[date] = None) -> int:
        """Reserve `count` API calls or raise DailyQuotaExceededError."""
        log = self._get_or_create_log(target_date)
        if log.request_count + count > log.daily_limit:
            raise DailyQuotaExceededError(
                f"Daily API quota exceeded ({log.request_count}/{log.daily_limit} used on {log.log_date})."
            )
        log.request_count += count
        log.last_called_at = datetime.now(timezone.utc)
        self.db.flush()
        return max(0, log.daily_limit - log.request_count)
