"""TSE Stocks Enterprise Module — ORM models (Additive, migration 0052).

  - stock_live_tape            → اسنپ‌شات زنده تابلو (upsert per symbol)
  - stock_order_book_l2        → دفتر سفارشات ۵ مظنه + OBI
  - stock_indicators_snapshot  → اندیکاتورهای پیش‌محاسبه روزانه
  - stock_quant_signals        → تاریخچه سیگنال کوانت
  - stock_news_sentiment       → اخبار + سنتیمنت NLP
  - stock_monthly_sales_production → گزارش فروش ماهانه کدال
  - market_macro_indicators    → متغیرهای کلان (دلار/اخزا/رژیم بازار)
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
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class StockLiveTapeModel(Base):
    """📺 اسنپ‌شات زنده تابلو — یک ردیف per symbol (upsert)."""

    __tablename__ = "stock_live_tape"

    symbol: Mapped[str] = mapped_column(String(50), primary_key=True)
    isin: Mapped[str | None] = mapped_column(String(20))
    last_price: Mapped[float | None] = mapped_column(Double)
    close_price: Mapped[float | None] = mapped_column(Double)
    yesterday_price: Mapped[float | None] = mapped_column(Double)
    price_first: Mapped[float | None] = mapped_column(Double)
    price_min: Mapped[float | None] = mapped_column(Double)
    price_max: Mapped[float | None] = mapped_column(Double)
    price_change_pct: Mapped[float | None] = mapped_column(Double)
    close_change_pct: Mapped[float | None] = mapped_column(Double)
    trade_volume: Mapped[int | None] = mapped_column(BigInteger)
    trade_value: Mapped[float | None] = mapped_column(Double)
    trade_count: Mapped[int | None] = mapped_column(BigInteger)
    buy_real_volume: Mapped[int | None] = mapped_column(BigInteger)
    sell_real_volume: Mapped[int | None] = mapped_column(BigInteger)
    buy_real_count: Mapped[int | None] = mapped_column(BigInteger)
    sell_real_count: Mapped[int | None] = mapped_column(BigInteger)
    buy_real_value: Mapped[float | None] = mapped_column(Double)
    sell_real_value: Mapped[float | None] = mapped_column(Double)
    buy_legal_volume: Mapped[int | None] = mapped_column(BigInteger)
    sell_legal_volume: Mapped[int | None] = mapped_column(BigInteger)
    buy_legal_value: Mapped[float | None] = mapped_column(Double)
    sell_legal_value: Mapped[float | None] = mapped_column(Double)
    buy_orders_json: Mapped[str | None] = mapped_column(Text)   # 5 مظنه خرید JSON
    sell_orders_json: Mapped[str | None] = mapped_column(Text)  # 5 مظنه فروش JSON
    base_volume: Mapped[int | None] = mapped_column(BigInteger)
    allowed_price_min: Mapped[float | None] = mapped_column(Double)
    allowed_price_max: Mapped[float | None] = mapped_column(Double)
    quoted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime)


class StockOrderBookL2Model(Base):
    """📚 اسنپ‌شات L2 دفتر سفارشات ۵ مظنه + شاخص OBI."""

    __tablename__ = "stock_order_book_l2"
    __table_args__ = (
        UniqueConstraint("symbol", "captured_at", name="uq_obl_symbol_ts"),
        Index("ix_obl_symbol_captured", "symbol", "captured_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(20))
    bids_json: Mapped[str] = mapped_column(Text, nullable=False)
    asks_json: Mapped[str] = mapped_column(Text, nullable=False)
    obi_5: Mapped[float | None] = mapped_column(Double)
    bid_queue_value: Mapped[float | None] = mapped_column(Double)
    ask_queue_value: Mapped[float | None] = mapped_column(Double)
    captured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class StockIndicatorsSnapshotModel(Base):
    """📐 اندیکاتورهای پیش‌محاسبه (Overnight Engine) — یک ردیف per (symbol, date)."""

    __tablename__ = "stock_indicators_snapshot"
    __table_args__ = (
        UniqueConstraint("symbol", "trade_date", name="uq_stock_ind"),
        Index("ix_stockind_date", "trade_date"),
    )

    symbol: Mapped[str] = mapped_column(String(50), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    rsi_14: Mapped[float | None] = mapped_column(Double)
    rsi_divergence: Mapped[str | None] = mapped_column(String(10))  # RD+|RD-|HD+|HD-|none
    macd: Mapped[float | None] = mapped_column(Double)
    macd_signal: Mapped[float | None] = mapped_column(Double)
    macd_hist: Mapped[float | None] = mapped_column(Double)
    ema_20: Mapped[float | None] = mapped_column(Double)
    ema_50: Mapped[float | None] = mapped_column(Double)
    ema_100: Mapped[float | None] = mapped_column(Double)
    ema_200: Mapped[float | None] = mapped_column(Double)
    ema_cross: Mapped[str | None] = mapped_column(String(20))
    bb_upper: Mapped[float | None] = mapped_column(Double)
    bb_middle: Mapped[float | None] = mapped_column(Double)
    bb_lower: Mapped[float | None] = mapped_column(Double)
    bb_squeeze: Mapped[bool | None] = mapped_column(Boolean)
    keltner_upper: Mapped[float | None] = mapped_column(Double)
    keltner_lower: Mapped[float | None] = mapped_column(Double)
    ichimoku_tenkan: Mapped[float | None] = mapped_column(Double)
    ichimoku_kijun: Mapped[float | None] = mapped_column(Double)
    ichimoku_senkou_a: Mapped[float | None] = mapped_column(Double)
    ichimoku_senkou_b: Mapped[float | None] = mapped_column(Double)
    ichimoku_state: Mapped[str | None] = mapped_column(String(20))
    atr_14: Mapped[float | None] = mapped_column(Double)
    mfi_14: Mapped[float | None] = mapped_column(Double)
    vwap_daily: Mapped[float | None] = mapped_column(Double)
    pivot_standard_json: Mapped[str | None] = mapped_column(Text)
    pivot_camarilla_json: Mapped[str | None] = mapped_column(Text)
    pivot_fibonacci_json: Mapped[str | None] = mapped_column(Text)
    trend_alignment_score: Mapped[float | None] = mapped_column(Double)
    computed_at: Mapped[datetime | None] = mapped_column(DateTime)


class StockQuantSignalModel(TimestampMixin, Base):
    """🎯 تاریخچه سیگنال کوانت — idempotent روی (symbol, signal_date)."""

    __tablename__ = "stock_quant_signals"
    __table_args__ = (
        UniqueConstraint("symbol", "signal_date", name="uq_stock_signal"),
        Index("ix_sig_symbol_date", "symbol", "signal_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(20))
    signal_date: Mapped[date] = mapped_column(Date, nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    composite_score: Mapped[float | None] = mapped_column(Double)
    tape_score: Mapped[float | None] = mapped_column(Double)
    tech_score: Mapped[float | None] = mapped_column(Double)
    fund_score: Mapped[float | None] = mapped_column(Double)
    peer_score: Mapped[float | None] = mapped_column(Double)
    macro_score: Mapped[float | None] = mapped_column(Double)
    entry_low: Mapped[float | None] = mapped_column(Double)
    entry_high: Mapped[float | None] = mapped_column(Double)
    stop_loss: Mapped[float | None] = mapped_column(Double)
    target_1: Mapped[float | None] = mapped_column(Double)
    target_2: Mapped[float | None] = mapped_column(Double)
    target_3: Mapped[float | None] = mapped_column(Double)
    risk_reward: Mapped[float | None] = mapped_column(Double)
    kelly_fraction: Mapped[float | None] = mapped_column(Double)
    position_size_pct: Mapped[float | None] = mapped_column(Double)
    market_regime: Mapped[str | None] = mapped_column(String(20))
    reasons_pro: Mapped[str | None] = mapped_column(Text)
    reasons_con: Mapped[str | None] = mapped_column(Text)
    engine_version: Mapped[str | None] = mapped_column(String(20))
    payload_json: Mapped[str | None] = mapped_column(Text)


class StockNewsSentimentModel(TimestampMixin, Base):
    """📰 اخبار + امتیاز سنتیمنت NLP (-1..+1)."""

    __tablename__ = "stock_news_sentiment"
    __table_args__ = (
        Index("ix_news_symbol_pub", "symbol", "published_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str | None] = mapped_column(String(50))
    isin: Mapped[str | None] = mapped_column(String(20))
    industry: Mapped[str | None] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(100))
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    sentiment: Mapped[str | None] = mapped_column(String(10))
    sentiment_score: Mapped[float | None] = mapped_column(Double)
    impact_tag: Mapped[str | None] = mapped_column(String(30))


class StockMonthlySalesModel(TimestampMixin, Base):
    """🏭 گزارش ماهانه تولید/فروش کدال — MoM/YoY محاسبه‌شده."""

    __tablename__ = "stock_monthly_sales_production"
    __table_args__ = (
        UniqueConstraint("symbol", "jalali_year", "jalali_month", "product_name",
                         name="uq_stock_monthly_sales"),
        Index("ix_msales_symbol", "symbol", "jalali_year", "jalali_month"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(20))
    jalali_year: Mapped[int] = mapped_column(Integer, nullable=False)
    jalali_month: Mapped[int] = mapped_column(Integer, nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False, default="-")
    sales_amount: Mapped[float | None] = mapped_column(Double)
    sales_volume: Mapped[float | None] = mapped_column(Double)
    unit_price: Mapped[float | None] = mapped_column(Double)
    sales_mom_pct: Mapped[float | None] = mapped_column(Double)
    sales_yoy_pct: Mapped[float | None] = mapped_column(Double)
    is_all_time_high: Mapped[bool | None] = mapped_column(Boolean)
    codal_letter_id: Mapped[str | None] = mapped_column(String(50))


class MarketMacroIndicatorModel(TimestampMixin, Base):
    """🌍 متغیرهای کلان روزانه — دلار نیما/آزاد، اخزا، رژیم بازار."""

    __tablename__ = "market_macro_indicators"
    __table_args__ = (
        UniqueConstraint("indicator_date", name="uq_macro_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    indicator_date: Mapped[date] = mapped_column(Date, nullable=False)
    usd_nima: Mapped[float | None] = mapped_column(Double)
    usd_free: Mapped[float | None] = mapped_column(Double)
    usd_gap_pct: Mapped[float | None] = mapped_column(Double)
    interbank_rate: Mapped[float | None] = mapped_column(Double)
    akhzar_ytm: Mapped[float | None] = mapped_column(Double)
    total_retail_value: Mapped[float | None] = mapped_column(Double)
    queue_buy_value: Mapped[float | None] = mapped_column(Double)
    queue_sell_value: Mapped[float | None] = mapped_column(Double)
    market_regime: Mapped[str | None] = mapped_column(String(20))
