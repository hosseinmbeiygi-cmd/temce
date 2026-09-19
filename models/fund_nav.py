"""موتور NAV مستقل + تطبیق مرجع — ORM Models (Additive-Only).

جداول:
  - fund_nav_runs               → اجرای محاسبه NAV مستقل (نسخه‌دار + input_hash)
  - fund_position_valuations    → ارزش ردیفی هر موقعیت
  - fund_nav_results            → NAV خالص و هر واحد
  - fund_nav_reference_reports  → گزارش NAV مرجع (آماری/صدور/ابطال)
  - fund_nav_reconciliation_runs    → نتیجه گیت‌ها + اختلاف
  - fund_nav_reconciliation_breaks  → پرونده مغایرت
  - fund_nav_thresholds         → آستانه دوگانه نسخه‌دار
  - fund_unit_movements         → دفتر واحدها

مرجع طراحی: ``docs/funds/NAV_ARCHITECTURE_V5.md`` (نسخه ۵.۱).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class FundNavRunModel(Base):
    """🧮 هر اجرای محاسبه NAV مستقل — قابل بازتولید با input_hash."""

    __tablename__ = "fund_nav_runs"
    __table_args__ = (
        UniqueConstraint(
            "fund_id", "valuation_date", "nav_type", "input_hash",
            name="uq_fund_nav_run",
        ),
        Index("ix_fund_nav_runs_fund_date", "fund_id", "valuation_date"),
        Index("ix_fund_nav_runs_quality", "quality_status", "valuation_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    valuation_date: Mapped[date] = mapped_column(Date, nullable=False)
    nav_type: Mapped[str] = mapped_column(String(16), nullable=False, default="STATISTICAL")
    mode: Mapped[str] = mapped_column(String(12), nullable=False, default="SHADOW")
    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    run_status: Mapped[str] = mapped_column(String(16), nullable=False, default="SUCCESS")
    quality_status: Mapped[str] = mapped_column(String(16), nullable=False, default="PARTIAL")
    holdings_period: Mapped[date | None] = mapped_column(Date)
    coverage_pct: Mapped[float | None] = mapped_column(Double)
    units_outstanding: Mapped[int | None] = mapped_column(BigInteger)
    total_assets: Mapped[float | None] = mapped_column(Double)
    total_liabilities: Mapped[float | None] = mapped_column(Double)
    net_assets: Mapped[float | None] = mapped_column(Double)
    nav_per_unit: Mapped[float | None] = mapped_column(Double)
    positions_count: Mapped[int] = mapped_column(Integer, default=0)
    source_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class FundPositionValuationModel(Base):
    """📄 ارزش ردیفی موقعیت — با منبع قیمت، زمان و کیفیت."""

    __tablename__ = "fund_position_valuations"
    __table_args__ = (
        Index("ix_fund_pos_val_run", "run_id"),
        Index("ix_fund_pos_val_fund", "fund_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("fund_nav_runs.id", ondelete="CASCADE"), nullable=False
    )
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    instrument_symbol: Mapped[str | None] = mapped_column(String(80))
    instrument_name: Mapped[str | None] = mapped_column(String(200))
    holding_type: Mapped[str] = mapped_column(String(30), nullable=False, default="other")
    quantity: Mapped[float | None] = mapped_column(Double)
    price: Mapped[float | None] = mapped_column(Double)
    price_source: Mapped[str | None] = mapped_column(String(24))
    price_at: Mapped[datetime | None] = mapped_column(DateTime)
    value: Mapped[float | None] = mapped_column(Double)
    weight_pct: Mapped[float | None] = mapped_column(Double)
    quality: Mapped[str | None] = mapped_column(String(16))
    reported_market_value: Mapped[float | None] = mapped_column(Double)
    note: Mapped[str | None] = mapped_column(String(300))


class FundNavResultModel(Base):
    """📊 نتیجه NAV مستقل — یک ردیف به‌ازای هر اجرا."""

    __tablename__ = "fund_nav_results"
    __table_args__ = (
        UniqueConstraint("run_id", name="uq_fund_nav_result_run"),
        Index("ix_fund_nav_results_fund", "fund_id", "valuation_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("fund_nav_runs.id", ondelete="CASCADE"), nullable=False
    )
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    nav_type: Mapped[str] = mapped_column(String(16), nullable=False)
    valuation_date: Mapped[date] = mapped_column(Date, nullable=False)
    net_assets: Mapped[float | None] = mapped_column(Double)
    units_outstanding: Mapped[int | None] = mapped_column(BigInteger)
    nav_per_unit: Mapped[float | None] = mapped_column(Double)
    quality_status: Mapped[str] = mapped_column(String(16), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(80))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class FundNavReferenceReportModel(Base):
    """📥 گزارش NAV مرجع — نسخه‌دار (آماری/صدور/ابطال)."""

    __tablename__ = "fund_nav_reference_reports"
    __table_args__ = (
        UniqueConstraint(
            "fund_id", "nav_date", "nav_type", "source", name="uq_fund_ref_report"
        ),
        Index("ix_fund_ref_reports_fund", "fund_id", "nav_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    nav_date: Mapped[date] = mapped_column(Date, nullable=False)
    nav_type: Mapped[str] = mapped_column(String(16), nullable=False)
    nav_value: Mapped[float] = mapped_column(Double, nullable=False)
    units_outstanding: Mapped[int | None] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="fund_nav_history")
    source_ref: Mapped[str | None] = mapped_column(String(120))
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    received_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    raw_json: Mapped[str | None] = mapped_column(Text)


class FundNavReconciliationRunModel(Base):
    """⚖️ اجرای تطبیق — سه بُعد وضعیت جدا (مقایسه‌پذیری/اعتبار مرجع/اختلاف)."""

    __tablename__ = "fund_nav_reconciliation_runs"
    __table_args__ = (
        Index("ix_fund_recon_fund_date", "fund_id", "valuation_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("fund_nav_runs.id", ondelete="SET NULL")
    )
    reference_report_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("fund_nav_reference_reports.id", ondelete="SET NULL")
    )
    nav_type: Mapped[str] = mapped_column(String(16), nullable=False)
    valuation_date: Mapped[date] = mapped_column(Date, nullable=False)
    comparability_status: Mapped[str] = mapped_column(String(16), nullable=False)
    reference_status: Mapped[str] = mapped_column(String(12), nullable=False)
    diff_status: Mapped[str | None] = mapped_column(String(12))
    internal_nav: Mapped[float | None] = mapped_column(Double)
    reference_nav: Mapped[float | None] = mapped_column(Double)
    abs_diff: Mapped[float | None] = mapped_column(Double)
    bps_diff: Mapped[float | None] = mapped_column(Double)
    abs_threshold: Mapped[float | None] = mapped_column(Double)
    bps_threshold: Mapped[float | None] = mapped_column(Double)
    threshold_version: Mapped[str | None] = mapped_column(String(32))
    probable_cause: Mapped[str | None] = mapped_column(Text)
    residual_unexplained: Mapped[float | None] = mapped_column(Double)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class FundNavReconciliationBreakModel(Base):
    """🛠 پرونده مغایرت — چرخه عمر و SLA."""

    __tablename__ = "fund_nav_reconciliation_breaks"
    __table_args__ = (
        Index("ix_fund_breaks_fund", "fund_id", "lifecycle"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    recon_run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("fund_nav_reconciliation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(16), nullable=False, default="OPEN")
    severity: Mapped[str] = mapped_column(String(12), nullable=False, default="WARNING")
    owner: Mapped[str | None] = mapped_column(String(80))
    opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime)
    evidence: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class FundNavThresholdModel(Base):
    """🎚 آستانه دوگانه نسخه‌دار — پیش‌فرض سراسری یا مخصوص هر صندوق."""

    __tablename__ = "fund_nav_thresholds"
    __table_args__ = (
        UniqueConstraint("fund_id", "nav_type", "version", name="uq_fund_nav_threshold"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False, default="*")
    nav_type: Mapped[str] = mapped_column(String(16), nullable=False, default="STATISTICAL")
    abs_warn: Mapped[float] = mapped_column(Double, nullable=False)
    abs_breach: Mapped[float] = mapped_column(Double, nullable=False)
    bps_warn: Mapped[float] = mapped_column(Double, nullable=False)
    bps_breach: Mapped[float] = mapped_column(Double, nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    effective_from: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    source_document_id: Mapped[str | None] = mapped_column(String(120))


class FundUnitMovementModel(Base):
    """🧾 دفتر واحدها — صدور/ابطال/توزیع/انتقال/توثیق."""

    __tablename__ = "fund_unit_movements"
    __table_args__ = (
        UniqueConstraint(
            "fund_id", "movement_date", "movement_type", "reference",
            name="uq_fund_unit_movement",
        ),
        Index("ix_fund_unit_moves_fund", "fund_id", "movement_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False)
    movement_date: Mapped[date] = mapped_column(Date, nullable=False)
    movement_type: Mapped[str] = mapped_column(String(24), nullable=False)
    units: Mapped[float] = mapped_column(Double, nullable=False)
    price_per_unit: Mapped[float | None] = mapped_column(Double)
    amount: Mapped[float | None] = mapped_column(Double)
    nav_type: Mapped[str | None] = mapped_column(String(16))
    reference: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
