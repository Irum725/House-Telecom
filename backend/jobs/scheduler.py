"""APScheduler configuration and InterestRegion job synchronization."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
except ImportError:
    BackgroundScheduler = None  # type: ignore[assignment]
    CronTrigger = None  # type: ignore[assignment]
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.jobs.diff import format_region_code
from backend.jobs.pipeline import run_weekly_pipeline
from shared.database import SessionLocal
from shared.models import InterestRegion

logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE = "Asia/Seoul"
JOB_ID_PREFIX = "interest_region_"

_scheduler: BackgroundScheduler | None = None


def run_scheduled_region_job(
    region_code: str,
    *,
    session_factory: sessionmaker[Session] = SessionLocal,
    use_fixture: bool = False,
    output_dir: str | Path | None = None,
) -> None:
    """Job entrypoint invoked by APScheduler for a single InterestRegion."""
    db = session_factory()
    try:
        run = run_weekly_pipeline(
            region_code,
            db=db,
            use_fixture=use_fixture,
            output_dir=output_dir,
        )
        logger.info(
            "Completed scheduled weekly report for region=%s run_id=%s total=%s new=%s changed=%s",
            region_code,
            run.id,
            run.total_count,
            run.new_count,
            run.stage_changed_count,
        )
    except Exception:
        logger.exception("Scheduled weekly report failed for region=%s", region_code)
        raise
    finally:
        db.close()


def sync_interest_region_jobs(
    scheduler: BackgroundScheduler,
    db: Session,
    *,
    session_factory: sessionmaker[Session] = SessionLocal,
    use_fixture: bool = False,
    output_dir: str | Path | None = None,
) -> list[str]:
    """Synchronize APScheduler cron jobs with active InterestRegion records."""
    active_regions = list(
        db.scalars(
            select(InterestRegion)
            .where(InterestRegion.is_active.is_(True))
            .order_by(InterestRegion.id.asc())
        ).all()
    )

    desired_ids: set[str] = set()
    for region in active_regions:
        job_id = f"{JOB_ID_PREFIX}{region.id}"
        desired_ids.add(job_id)
        region_code = format_region_code(region.sigungu_cd, region.bjdong_cd)
        trigger = CronTrigger.from_crontab(region.cron_expr, timezone=DEFAULT_TIMEZONE)
        scheduler.add_job(
            run_scheduled_region_job,
            trigger=trigger,
            id=job_id,
            name=f"Weekly Report: {region.name} ({region_code})",
            kwargs={
                "region_code": region_code,
                "session_factory": session_factory,
                "use_fixture": use_fixture,
                "output_dir": output_dir,
            },
            replace_existing=True,
        )

    for existing_job in scheduler.get_jobs():
        if existing_job.id.startswith(JOB_ID_PREFIX) and existing_job.id not in desired_ids:
            scheduler.remove_job(existing_job.id)

    return sorted(desired_ids)


def create_scheduler(
    *,
    session_factory: sessionmaker[Session] = SessionLocal,
    sync_from_db: bool = True,
    use_fixture: bool = False,
    output_dir: str | Path | None = None,
) -> BackgroundScheduler | None:
    """Create and optionally populate a BackgroundScheduler from active InterestRegions."""
    if BackgroundScheduler is None:
        logger.warning("apscheduler is not installed; background scheduler is disabled.")
        return None

    scheduler = BackgroundScheduler(timezone=DEFAULT_TIMEZONE)
    if sync_from_db:
        db = session_factory()
        try:
            sync_interest_region_jobs(
                scheduler,
                db,
                session_factory=session_factory,
                use_fixture=use_fixture,
                output_dir=output_dir,
            )
        finally:
            db.close()
    return scheduler


def get_scheduler() -> BackgroundScheduler | None:
    """Return the active module-level scheduler, if started."""
    return _scheduler


def start_scheduler(
    *,
    session_factory: sessionmaker[Session] = SessionLocal,
    use_fixture: bool = False,
    output_dir: str | Path | None = None,
) -> BackgroundScheduler:
    """Start the singleton BackgroundScheduler (idempotent)."""
    global _scheduler
    if BackgroundScheduler is None:
        logger.warning("apscheduler is not installed; skipping start_scheduler.")
        return None  # type: ignore[return-value]

    if _scheduler is not None and _scheduler.running:
        return _scheduler
    _scheduler = create_scheduler(
        session_factory=session_factory,
        sync_from_db=True,
        use_fixture=use_fixture,
        output_dir=output_dir,
    )
    _scheduler.start()
    return _scheduler


def stop_scheduler(*, wait: bool = False) -> None:
    """Shut down the singleton BackgroundScheduler if running."""
    global _scheduler
    if _scheduler is not None:
        if _scheduler.running:
            _scheduler.shutdown(wait=wait)
        _scheduler = None


def list_scheduled_jobs(scheduler: BackgroundScheduler | None = None) -> list[dict[str, Any]]:
    """Return a summary list of registered APScheduler jobs."""
    target = scheduler or _scheduler
    if target is None:
        return []
    result: list[dict[str, Any]] = []
    for job in target.get_jobs():
        next_run = getattr(job, "next_run_time", None)
        result.append(
            {
                "id": job.id,
                "name": job.name,
                "next_run_time": next_run.isoformat() if next_run else None,
                "trigger": str(job.trigger),
            }
        )
    return result
