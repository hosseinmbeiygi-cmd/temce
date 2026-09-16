"""مدل‌های ORM صندوق‌یار — جداول اصلی پایگاه داده.

این مدل‌ها با SQLAlchemy ساخته شده‌اند. جداول:
- funds: صندوق‌ها
- peer_group: تخصیص هم‌گروه (type_code + aum_band)
- scoring_config_history: نسخه‌بندی وزن‌ها
- fund_metrics: شاخص‌های محاسبه‌شده (TS-friendly از طریق TimescaleDB hypertable)
- bubble_snapshots: P/NAV لحظه‌ای
- alerts: هشدارهای per-user
- data_conflicts: تعارض داده بین Adapterها
- adapter_health: وضعیت سلامت Adapterها
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from core.time import utc_now_naive


class Base(DeclarativeBase):
    """پایه مشترک برای همه مدل‌های صندوق‌یار."""


class Fund(Base):
    """جدول اصلی صندوق‌ها."""

    __tablename__ = "funds"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    name_fa: Mapped[str] = mapped_column(String(200), nullable=False)
    type_code: Mapped[str] = mapped_column(String(4), nullable=False, index=True)
    aum_band: Mapped[str | None] = mapped_column(String(1))
    manager: Mapped[str | None] = mapped_column(String(100))
    custodian: Mapped[str | None] = mapped_column(String(100))
    auditor: Mapped[str | None] = mapped_column(String(100))
    market_maker: Mapped[str | None] = mapped_column(String(100))
    inception_date: Mapped[datetime | None] = mapped_column(DateTime)
    is_etf: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

    metrics: Mapped[list[FundMetric]] = relationship(back_populates="fund")

    __table_args__ = (Index("ix_funds_type_active", "type_code", "is_active"),)


class ScoringConfigHistory(Base):
    """نسخه‌بندی وزن‌های Scoring Engine — قابلیت بازتولید تاریخی."""

    __tablename__ = "scoring_config_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    type_code: Mapped[str] = mapped_column(String(4), nullable=False)
    weights_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON: {metric_key: weight}
    thresholds_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    created_by: Mapped[str | None] = mapped_column(String(100))
    change_reason: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (UniqueConstraint("version", "type_code", name="uq_scoring_version_type"),)


class FundMetric(Base):
    """شاخص‌های محاسبه‌شده برای هر صندوق در یک تاریخ.

    در عمل به‌صورت TimescaleDB hypertable روی (symbol, ts) درج می‌شود.
    """

    __tablename__ = "fund_metrics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), ForeignKey("funds.symbol", ondelete="CASCADE"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)

    # لایه ۱
    return_1m: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    return_3m: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    return_6m: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    return_1y: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    return_3y: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    return_inception: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    p_nav_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    aum_btoman: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    daily_volume: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    bid_ask_spread: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))

    # لایه ۲
    sharpe: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    sortino: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    calmar: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    max_drawdown: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    recovery_days: Mapped[int | None] = mapped_column(Integer)
    beta: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    std_dev: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    info_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    upside_capture: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    downside_capture: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))

    # لایه ۳ — ساختار و هزینه (۱۰)
    active_share: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    bootstrap_alpha_pvalue: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    style_drift: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    ter: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    performance_fee_type: Mapped[str | None] = mapped_column(String(20))
    hhi: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    turnover: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    cash_drag: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    window_dressing: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    tracking_difference: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))

    # لایه ۴ — رفتاری و کوانت (۱۲)
    behavior_gap: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    survivorship_flag: Mapped[bool | None] = mapped_column(Boolean)
    liquidity_spiral: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    hidden_leverage: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    benchmark_gaming: Mapped[bool | None] = mapped_column(Boolean)
    performance_persistence: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    market_timing: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    flow_performance: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    redemption_pressure: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    diseconomies_of_scale: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    manager_tenure_days: Mapped[int | None] = mapped_column(Integer)
    post_change_alpha: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    fund_family_correlation: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))

    # لایه ۵ — ایران (۱۸)
    fx_beta_nima: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    fx_beta_azad: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    inflation_beta: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    real_return: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    geopolitical_sensitivity: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    calendar_esfand: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    calendar_khordad: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    calendar_ramadan: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    interbank_rate_beta: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    duration_years: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    gold_world_corr: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    silver_world_corr: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    saffron_corr: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    peer_correlation: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    pnav_peer_percentile: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    liquidity_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    order_book_depth: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))

    # امتیاز نهایی
    score_total: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    score_return: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    score_risk: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    score_cost: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    score_liquidity: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    signal: Mapped[str | None] = mapped_column(String(20))
    scoring_version: Mapped[str | None] = mapped_column(String(20))
    cold_start_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))

    fund: Mapped[Fund] = relationship(back_populates="metrics")

    __table_args__ = (
        UniqueConstraint("symbol", "ts", "window_days", name="uq_fund_metric_ts_window"),
        Index("ix_fund_metrics_signal", "signal"),
    )


class BubbleSnapshot(Base):
    """P/NAV لحظه‌ای برای Bubble Monitor."""

    __tablename__ = "bubble_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), ForeignKey("funds.symbol"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    nav: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    market_price: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    bubble_pct: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    type_code: Mapped[str] = mapped_column(String(4), nullable=False, index=True)
    peer_median_bubble: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))

    __table_args__ = (Index("ix_bubble_type_ts", "type_code", "ts"),)


class Alert(Base):
    """هشدارهای per-user."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    symbol: Mapped[str | None] = mapped_column(String(20))
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)


class DataConflict(Base):
    """تعارض داده بین Adapterها — ثبت برای Audit."""

    __tablename__ = "data_conflicts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    field: Mapped[str] = mapped_column(String(50), nullable=False)
    source_a: Mapped[str] = mapped_column(String(50), nullable=False)
    value_a: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    source_b: Mapped[str] = mapped_column(String(50), nullable=False)
    value_b: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    winner_source: Mapped[str] = mapped_column(String(50))
    ts: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, index=True)


class AdapterHealth(Base):
    """وضعیت سلامت هر Adapter."""

    __tablename__ = "adapter_health"

    name: Mapped[str] = mapped_column(String(50), primary_key=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    circuit_state: Mapped[str] = mapped_column(String(20), default="closed")
    total_calls: Mapped[int] = mapped_column(Integer, default=0)
    total_errors: Mapped[int] = mapped_column(Integer, default=0)
    avg_latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)


class FundManagerHistory(Base):
    """تاریخچه تغییر مدیر صندوق — برای Post-Change Alpha Event Study."""

    __tablename__ = "fund_manager_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), ForeignKey("funds.symbol"), index=True)
    manager_name: Mapped[str] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    source: Mapped[str] = mapped_column(String(50), default="codal")


class PeerGroupOverride(Base):
    """Override دستی هم‌گروه (برای صندوق‌های بخشی با زیرگروه)."""

    __tablename__ = "peer_group_override"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    peer_type_code: Mapped[str] = mapped_column(String(4), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)
