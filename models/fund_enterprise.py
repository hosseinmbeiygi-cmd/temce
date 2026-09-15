"""Enterprise Fund Module — ORM models (Additive-Only, Zero Breaking Changes).

جداول جدید ماژول ارتقایافته صندوق‌ها:
  - fund_capabilities          → فلگ‌های قابلیت هر صندوق
  - fund_nav_history           → تاریخچه NAV (idempotent روی fund_id+nav_date)
  - fund_portfolio_reports     → سربرگ گزارش ماهانه کدال
  - fund_holdings              → ریز دارایی‌ها
  - fund_portfolio_diffs       → تغییرات وزنی/ورود و خروج پول
  - fund_market_quotes_cache   → کش قیمت لحظه‌ای
  - fund_scores_history        → تاریخچه امتیاز دوره‌ای
  - fund_ingestion_quarantine  → قرنطینه داده مخرب

کلید کانونی صندوق: اولاً ISIN، ثانیاً national_id — مستقل از نماد.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Double,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class FundCapabilityModel(TimestampMixin, Base):
    """⚙️ فلگ‌های تشخیصی خودکار هر صندوق (کشف‌شده از داده)."""

    __tablename__ = "fund_capabilities"
    __table_args__ = (
        UniqueConstraint("fund_id", name="uq_fund_capabilities_fund"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    isin: Mapped[str | None] = mapped_column(String(20))
    has_nav: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_portfolio: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_etf: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_market_quotes: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_codal_reports: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    capabilities_json: Mapped[str | None] = mapped_column(Text)


class FundNavHistoryModel(TimestampMixin, Base):
    """📈 تاریخچه NAV — یک ردیف به‌ازای (fund_id, nav_date)."""

    __tablename__ = "fund_nav_history"
    __table_args__ = (
        UniqueConstraint("fund_id", "nav_date", name="uq_fund_nav"),
        Index("ix_fund_nav_fund_date", "fund_id", "nav_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    isin: Mapped[str | None] = mapped_column(String(20))
    nav_date: Mapped[date] = mapped_column(Date, nullable=False)
    nav_date_greg: Mapped[date | None] = mapped_column(Date)
    nav_issue: Mapped[float | None] = mapped_column(Double, comment="NAV صدور")
    nav_redemption: Mapped[float | None] = mapped_column(Double, comment="NAV ابطال")
    nav_statistical: Mapped[float | None] = mapped_column(Double, comment="قیمت آماری")
    total_asset_value: Mapped[float | None] = mapped_column(Double)
    units_outstanding: Mapped[int | None] = mapped_column(BigInteger)
    data_source: Mapped[str] = mapped_column(String(30), nullable=False, default="api")
    payload_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)


class FundPortfolioReportModel(TimestampMixin, Base):
    """📋 سربرگ گزارش ماهانه کدال (دوره منتهی به period_end_date)."""

    __tablename__ = "fund_portfolio_reports"
    __table_args__ = (
        UniqueConstraint("fund_id", "period_end_date", name="uq_fund_report_period"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    isin: Mapped[str | None] = mapped_column(String(20))
    period_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_end_date_greg: Mapped[date | None] = mapped_column(Date)
    publish_date: Mapped[date | None] = mapped_column(Date)
    codal_letter_id: Mapped[str | None] = mapped_column(String(50))
    report_title: Mapped[str | None] = mapped_column(String(300))
    total_assets: Mapped[float | None] = mapped_column(Double)
    total_liabilities: Mapped[float | None] = mapped_column(Double)
    net_asset_value: Mapped[float | None] = mapped_column(Double)
    units_outstanding: Mapped[int | None] = mapped_column(BigInteger)
    cash_and_equivalents: Mapped[float | None] = mapped_column(Double)
    data_source: Mapped[str] = mapped_column(String(30), nullable=False, default="api")
    payload_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)


class FundHoldingModel(TimestampMixin, Base):
    """🧩 ریز دارایی صندوق — سهام، اوراق، سپرده، طلا، مشتقات."""

    __tablename__ = "fund_holdings"
    __table_args__ = (
        UniqueConstraint(
            "fund_id", "period_end_date", "holding_type", "instrument_symbol",
            name="uq_fund_holding",
        ),
        Index("ix_fund_holdings_fund", "fund_id", "period_end_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    report_id: Mapped[int | None] = mapped_column(BigInteger)
    period_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    holding_type: Mapped[str] = mapped_column(String(30), nullable=False)
    instrument_symbol: Mapped[str | None] = mapped_column(String(50))
    instrument_name: Mapped[str | None] = mapped_column(String(200))
    instrument_isin: Mapped[str | None] = mapped_column(String(20))
    quantity: Mapped[float | None] = mapped_column(Double)
    book_value: Mapped[float | None] = mapped_column(Double)
    market_value: Mapped[float | None] = mapped_column(Double)
    weight_pct: Mapped[float | None] = mapped_column(Double)
    data_source: Mapped[str] = mapped_column(String(30), nullable=False, default="api")
    payload_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)


class FundPortfolioDiffModel(TimestampMixin, Base):
    """🔀 تغییرات وزنی بین دو دوره — ورود/خروج پول صندوق به نمادها."""

    __tablename__ = "fund_portfolio_diffs"
    __table_args__ = (
        UniqueConstraint(
            "fund_id", "current_period_date", "instrument_symbol",
            name="uq_fund_diff",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    instrument_symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    current_period_date: Mapped[date] = mapped_column(Date, nullable=False)
    previous_period_date: Mapped[date | None] = mapped_column(Date)
    prev_weight_pct: Mapped[float | None] = mapped_column(Double)
    curr_weight_pct: Mapped[float | None] = mapped_column(Double)
    weight_change_pct: Mapped[float | None] = mapped_column(Double)
    prev_market_value: Mapped[float | None] = mapped_column(Double)
    curr_market_value: Mapped[float | None] = mapped_column(Double)
    flow_direction: Mapped[str | None] = mapped_column(String(10))  # in|out|new|exited|hold


class FundMarketQuoteCacheModel(TimestampMixin, Base):
    """⚡ کش قیمت لحظه‌ای بازار صندوق (TTL پایین — فقط آخرین وضعیت)."""

    __tablename__ = "fund_market_quotes_cache"
    __table_args__ = (
        UniqueConstraint("fund_id", name="uq_fund_quote"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str | None] = mapped_column(String(50), index=True)
    last_price: Mapped[float | None] = mapped_column(Double)
    close_price: Mapped[float | None] = mapped_column(Double)
    yesterday_price: Mapped[float | None] = mapped_column(Double)
    bid_price: Mapped[float | None] = mapped_column(Double)
    ask_price: Mapped[float | None] = mapped_column(Double)
    bid_volume: Mapped[int | None] = mapped_column(BigInteger)
    ask_volume: Mapped[int | None] = mapped_column(BigInteger)
    trade_volume: Mapped[int | None] = mapped_column(BigInteger)
    trade_value: Mapped[float | None] = mapped_column(Double)
    market_value: Mapped[float | None] = mapped_column(Double)
    price_change_pct: Mapped[float | None] = mapped_column(Double)
    quoted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class FundScoreHistoryModel(TimestampMixin, Base):
    """🏅 تاریخچه امتیازدهی و رتبه‌بندی دوره‌ای صندوق."""

    __tablename__ = "fund_scores_history"
    __table_args__ = (
        UniqueConstraint("fund_id", "score_date", name="uq_fund_score"),
        Index("ix_fund_scores_rank", "score_date", "rank_overall"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    fund_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    score_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_score: Mapped[float | None] = mapped_column(Double)
    return_score: Mapped[float | None] = mapped_column(Double)
    risk_score: Mapped[float | None] = mapped_column(Double)
    liquidity_score: Mapped[float | None] = mapped_column(Double)
    stability_score: Mapped[float | None] = mapped_column(Double)
    sharpe: Mapped[float | None] = mapped_column(Double)
    sortino: Mapped[float | None] = mapped_column(Double)
    max_drawdown: Mapped[float | None] = mapped_column(Double)
    calmar: Mapped[float | None] = mapped_column(Double)
    alpha: Mapped[float | None] = mapped_column(Double)
    beta: Mapped[float | None] = mapped_column(Double)
    rank_overall: Mapped[int | None] = mapped_column(Integer)
    rank_in_type: Mapped[int | None] = mapped_column(Integer)
    engine_version: Mapped[str | None] = mapped_column(String(20))
    payload_json: Mapped[str | None] = mapped_column(Text)


class FundIngestionQuarantineModel(TimestampMixin, Base):
    """🚫 قرنطینه داده‌های نامعتبر — مانع از تراکنش بقیه داده‌ها نمی‌شود."""

    __tablename__ = "fund_ingestion_quarantine"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_endpoint: Mapped[str | None] = mapped_column(String(100))
    fund_id: Mapped[str | None] = mapped_column(String(50), index=True)
    isin: Mapped[str | None] = mapped_column(String(20))
    record_fingerprint: Mapped[str | None] = mapped_column(String(120), index=True)
    payload_json: Mapped[str | None] = mapped_column(Text)
    reject_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    reject_rule: Mapped[str | None] = mapped_column(String(100))
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
