"""SQLAlchemy 2.0 ORM models (SQLite dev / PostgreSQL-compatible)."""

from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database import Base
from shared.enums import BuildingStage, ExclusionStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Region(Base):
    """법정동코드 (행정표준코드 10자리) table."""

    __tablename__ = "regions"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    sido_cd: Mapped[str] = mapped_column(String(2), index=True, nullable=False)
    sigungu_cd: Mapped[str] = mapped_column(String(5), index=True, nullable=False)
    bjdong_cd: Mapped[str] = mapped_column(String(5), index=True, nullable=False)
    sido_name: Mapped[str] = mapped_column(String(50), nullable=False)
    sigungu_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    emd_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    __table_args__ = (
        Index("ix_regions_hierarchy", "sido_cd", "sigungu_cd", "bjdong_cd"),
    )


class Building(Base):
    """건축HUB 인허가 기반 신축/인허가 건축물 마스터 테이블."""

    __tablename__ = "buildings"

    mgm_pmsrgst_pk: Mapped[str] = mapped_column(String(64), primary_key=True)
    bld_rgst_pk: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    sigungu_cd: Mapped[str] = mapped_column(String(5), index=True, nullable=False)
    bjdong_cd: Mapped[str] = mapped_column(String(5), index=True, nullable=False)
    plat_plc: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bld_nm: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    main_purps_cd_nm: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    tot_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hhld_cnt: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    dong_cnt: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    arch_pms_day: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    stcns_sched_day: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    real_stcns_day: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    use_apr_day: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)

    stage: Mapped[BuildingStage] = mapped_column(
        SAEnum(BuildingStage, native_enum=False, length=32),
        default=BuildingStage.PERMITTED,
        nullable=False,
        index=True,
    )
    priority_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, index=True)
    raw_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    exclusions: Mapped[list["ExclusionHistory"]] = relationship(
        back_populates="building",
        cascade="all, delete-orphan",
        order_by="desc(ExclusionHistory.created_at)",
    )

    __table_args__ = (
        Index("ix_buildings_region", "sigungu_cd", "bjdong_cd"),
    )


class ExclusionHistory(Base):
    """제외(개통완료/비대상/보류) 및 복원 이력 테이블."""

    __tablename__ = "exclusion_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mgm_pmsrgst_pk: Mapped[str] = mapped_column(
        ForeignKey("buildings.mgm_pmsrgst_pk", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    status: Mapped[ExclusionStatus] = mapped_column(
        SAEnum(ExclusionStatus, native_enum=False, length=32),
        nullable=False,
        index=True,
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    restored_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    restored_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    building: Mapped["Building"] = relationship(back_populates="exclusions")


class InterestRegion(Base):
    """스케줄러 자동 수집 및 리포트 대상 관심 지역."""

    __tablename__ = "interest_regions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sigungu_cd: Mapped[str] = mapped_column(String(5), nullable=False, index=True)
    bjdong_cd: Mapped[str] = mapped_column(String(5), default="00000", nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    cron_expr: Mapped[str] = mapped_column(String(64), default="0 6 * * 1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class ReportRun(Base):
    """리포트 생성 및 스케줄러 실행 이력 테이블."""

    __tablename__ = "report_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region_code: Mapped[str] = mapped_column(String(10), index=True, nullable=False)
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )
    excel_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    new_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stage_changed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    diff_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)


class ApiTrafficLog(Base):
    """공공데이터포털(data.go.kr) 일일 API 호출량 추적 (기본 10,000건 제한)."""

    __tablename__ = "api_traffic_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    log_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    daily_limit: Mapped[int] = mapped_column(Integer, default=10000, nullable=False)
    last_called_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
