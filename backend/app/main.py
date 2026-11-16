"""FastAPI application entrypoint for House-Telecom."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.jobs.scheduler import start_scheduler, stop_scheduler
from backend.region.service import ensure_regions_seeded
from backend.routers import buildings, dashboard, exclusions, jobs, regions, reports
from shared.database import SessionLocal, init_db

logger = logging.getLogger(__name__)


def _get_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:4002,http://127.0.0.1:4002,http://localhost:5173,http://127.0.0.1:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize database schema, seed legal-dong regions, and manage scheduler."""
    init_db()
    db = SessionLocal()
    try:
        ensure_regions_seeded(db)
    finally:
        db.close()

    scheduler_started = False
    disable_scheduler = os.getenv("DISABLE_SCHEDULER", "").lower() in {"1", "true", "yes"}
    if not disable_scheduler and "PYTEST_CURRENT_TEST" not in os.environ:
        try:
            start_scheduler()
            scheduler_started = True
        except Exception:
            logger.exception("Failed to start background scheduler")

    try:
        yield
    finally:
        if scheduler_started:
            stop_scheduler()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    init_db()
    with SessionLocal() as db:
        ensure_regions_seeded(db)

    application = FastAPI(
        title="House-Telecom API",
        version="0.1.0",
        description="신축·인허가 건축물 통신영업 타겟 발굴 및 공정 단계별 자동 리포팅 플랫폼 REST API",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=_get_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    @application.exception_handler(ValueError)
    async def value_error_handler(_request: Request, exc: ValueError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception):
        logger.exception("Unhandled server error: %s", exc)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    @application.get("/api/health", tags=["health"])
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    application.include_router(regions.router)
    application.include_router(buildings.router)
    application.include_router(exclusions.router)
    application.include_router(reports.router)
    application.include_router(dashboard.router)
    application.include_router(jobs.router)

    dist_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if dist_dir.exists():
        application.mount("/", StaticFiles(directory=dist_dir, html=True), name="static")

    return application


app = create_app()


def application(environ, start_response):
    """Lazy WSGI bridge to avoid circular import."""
    from backend.app.wsgi import application as _app

    return _app(environ, start_response)


wsgi_app = application
