"""SQLAlchemy models برای GoldDesk — ۵ جدول.

هر ۵ دقیقه یک snapshot. NAV روزانه صندوق‌ها. قوانین alert + رویدادها. تاریخچه امتیاز.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class GoldDeskBase(DeclarativeBase):
    """پایه مشترک."""

    pass


class GoldSnapshotModel(GoldDeskBase):
    """هر ۵ دقیقه یک ردیف برای هر symbol طلا/سکه + محاسبات."""

    __tablename__ = "gold_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(16), nullable=False)  # gold, coin, fx, fund

    market_price: Mapped[float] = mapped_column(Float, nullable=False)
    fair_value: Mapped[float | None] = mapped_column(Float)
    bubble_abs: Mapped[float | None] = mapped_column(Float)
    bubble_pct: Mapped[float | None] = mapped_column(Float)
    implied_usd: Mapped[float | None] = mapped_column(Float)

    # مرجع‌ها
    xau_usd: Mapped[float | None] = mapped_column(Float)
    usd_irt: Mapped[float | None] = mapped_column(Float)
    aed_irt: Mapped[float | None] = mapped_column(Float)
    aed_parity_usd: Mapped[float | None] = mapped_column(Float)
    aed_gap_pct: Mapped[float | None] = mapped_column(Float)

    # meta
    quality_flag: Mapped[str] = mapped_column(String(16), default="clean")
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    __table_args__ = (Index("ix_snap_symbol_time", "symbol", "snapshot_at"),)


class GoldFundNAVModel(GoldDeskBase):
    """NAV روزانه صندوق‌های طلا + حباب P/NAV."""

    __tablename__ = "gold_fund_nav"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    fund_name: Mapped[str] = mapped_column(String(64), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    nav_per_unit: Mapped[float] = mapped_column(Float, nullable=False)
    market_price: Mapped[float] = mapped_column(Float, nullable=False)
    bubble_abs: Mapped[float] = mapped_column(Float, default=0)
    bubble_pct: Mapped[float] = mapped_column(Float, default=0)
    units_traded: Mapped[int] = mapped_column(BigInteger, default=0)
    real_buy_value: Mapped[int] = mapped_column(BigInteger, default=0)
    real_sell_value: Mapped[int] = mapped_column(BigInteger, default=0)
    bpr: Mapped[float] = mapped_column(Float, default=0)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_fundnav_symbol_date", "symbol", "date", unique=True),)


class AlertRuleModel(GoldDeskBase):
    """قوانین اعلان — کاربر تعریف می‌کند."""

    __tablename__ = "gold_alert_rules"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # bubble_above | bubble_below | nav_bubble_above | score_above | score_below
    # | price_above | price_below | parity_gap_above | rsi_below | rsi_above
    symbol: Mapped[str | None] = mapped_column(String(32), index=True)  # None = all
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    channel: Mapped[str] = mapped_column(String(16), default="inapp")  # inapp | telegram | both
    telegram_chat_id: Mapped[str | None] = mapped_column(String(32))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=30)
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AlertEventModel(GoldDeskBase):
    """رویدادهای اعلان شده."""

    __tablename__ = "gold_alert_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("gold_alert_rules.id", ondelete="CASCADE"), nullable=False
    )
    rule_name: Mapped[str | None] = mapped_column(String(64))
    symbol: Mapped[str | None] = mapped_column(String(32))
    trigger_value: Mapped[float | None] = mapped_column(Float)
    threshold: Mapped[float | None] = mapped_column(Float)
    message: Mapped[str | None] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(16), default="inapp")
    sent_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class GoldScoreHistoryModel(GoldDeskBase):
    """ذخیره امتیاز ۰-۱۰۰ هر ۵ دقیقه برای نمودار."""

    __tablename__ = "gold_score_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    components_json: Mapped[str] = mapped_column(Text)  # JSON
    decision: Mapped[str] = mapped_column(String(16))  # GREEN | YELLOW | RED
    hard_stop_active: Mapped[bool] = mapped_column(Boolean, default=False)
    hard_stop_reason: Mapped[str | None] = mapped_column(String(256))
    score_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class GoldHoldingModel(GoldDeskBase):
    """هر خرید ثبت‌شده. quantity * buy_price = مبلغ سرمایه‌گذاری."""

    __tablename__ = "gold_holdings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    vehicle: Mapped[str] = mapped_column(String(16), default="etf")
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    buy_price: Mapped[float] = mapped_column(Float, nullable=False)
    buy_amount_irt: Mapped[float] = mapped_column(Float, nullable=False)
    buy_fee_pct: Mapped[float] = mapped_column(Float, default=0)
    bought_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    note: Mapped[str | None] = mapped_column(String(256), nullable=True)


class GoldDCAPlanModel(GoldDeskBase):
    """پلن DCA با ۳ پله."""

    __tablename__ = "gold_dca_plans"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    total_capital_irt: Mapped[float] = mapped_column(Float, nullable=False)
    risk_profile: Mapped[str] = mapped_column(String(16), default="balanced")
    vehicle: Mapped[str] = mapped_column(String(16), default="etf")
    ladder_json: Mapped[str] = mapped_column(Text, nullable=False)
    executed_tranches: Mapped[int] = mapped_column(BigInteger, default=0)
    current_score: Mapped[int] = mapped_column(BigInteger, default=0)
    stop_loss_pct: Mapped[float] = mapped_column(Float, default=8.0)
    take_profit_pct: Mapped[float] = mapped_column(Float, default=25.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GoldTradeModel(GoldDeskBase):
    """معاملات ثبت‌شده (buy/sell)."""

    __tablename__ = "gold_trades"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    holding_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("gold_holdings.id", ondelete="CASCADE"), nullable=True
    )
    plan_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("gold_dca_plans.id", ondelete="SET NULL"), nullable=True
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(8), nullable=False)  # buy | sell
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    amount_irt: Mapped[float] = mapped_column(Float, nullable=False)
    fee_irt: Mapped[float] = mapped_column(Float, default=0)
    pnl_irt: Mapped[float] = mapped_column(Float, default=0)
    note: Mapped[str | None] = mapped_column(String(256), nullable=True)
    traded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


# ── Helper: تشخیص اینکه آیا جداول در Base هستند (برای Alembic) ──
__all__ = [
    "GoldDeskBase",
    "GoldSnapshotModel",
    "GoldFundNAVModel",
    "AlertRuleModel",
    "AlertEventModel",
    "GoldScoreHistoryModel",
    "GoldHoldingModel",
    "GoldDCAPlanModel",
    "GoldTradeModel",
]
