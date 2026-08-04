"""
TSETMC ORM models for the BrsApi integration.

Each model stores a single snapshot type from one BrsApi TSETMC endpoint.
All tables use the ``brsapi_`` prefix.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from brsapi.models.base import BrsApiBase, InstrumentRefMixin


class BooleanDefaultFalse(Boolean):
    """Boolean column type that creates no constraint (for nullable bools)."""
    def __init__(self) -> None:
        super().__init__(create_constraint=False)


class SymbolSnapshotModel(InstrumentRefMixin, BrsApiBase):
    """
    Realtime snapshot of a single symbol from ``AllSymbols.php``.

    This is the core realtime price & volume data table. One row per
    symbol per fetch cycle.
    """

    __tablename__ = "brsapi_symbol_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ins_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    isin: Mapped[str | None] = mapped_column(String(50), index=True)
    sector: Mapped[str | None] = mapped_column(String(100))
    sector_id: Mapped[int | None] = mapped_column(Integer)

    # Fundamental
    shares_count: Mapped[int | None] = mapped_column(BigInteger)
    base_volume: Mapped[int | None] = mapped_column(BigInteger)
    market_value: Mapped[float | None] = mapped_column(Float)
    eps: Mapped[float | None] = mapped_column(Float)
    pe_ratio: Mapped[float | None] = mapped_column(Float)

    # Price
    price_min: Mapped[float | None] = mapped_column(Float)
    price_max: Mapped[float | None] = mapped_column(Float)
    price_yesterday: Mapped[float | None] = mapped_column(Float)
    price_first: Mapped[float | None] = mapped_column(Float)
    price_last: Mapped[float | None] = mapped_column(Float)
    price_last_change: Mapped[float | None] = mapped_column(Float)
    price_last_change_pct: Mapped[float | None] = mapped_column(Float)
    price_close: Mapped[float | None] = mapped_column(Float)
    price_close_change: Mapped[float | None] = mapped_column(Float)
    price_close_change_pct: Mapped[float | None] = mapped_column(Float)

    # Trade
    trade_count: Mapped[int | None] = mapped_column(Integer)
    trade_volume: Mapped[int | None] = mapped_column(BigInteger)
    trade_value: Mapped[float | None] = mapped_column(Float)

    # Real / Legal
    buy_real_count: Mapped[int | None] = mapped_column(Integer)
    buy_legal_count: Mapped[int | None] = mapped_column(Integer)
    sell_real_count: Mapped[int | None] = mapped_column(Integer)
    sell_legal_count: Mapped[int | None] = mapped_column(Integer)
    buy_real_volume: Mapped[int | None] = mapped_column(BigInteger)
    buy_legal_volume: Mapped[int | None] = mapped_column(BigInteger)
    sell_real_volume: Mapped[int | None] = mapped_column(BigInteger)
    sell_legal_volume: Mapped[int | None] = mapped_column(BigInteger)

    # Orderbook (5 levels bid)
    bid_count_1: Mapped[int | None] = mapped_column(Integer)
    bid_volume_1: Mapped[int | None] = mapped_column(BigInteger)
    bid_price_1: Mapped[float | None] = mapped_column(Float)
    bid_count_2: Mapped[int | None] = mapped_column(Integer)
    bid_volume_2: Mapped[int | None] = mapped_column(BigInteger)
    bid_price_2: Mapped[float | None] = mapped_column(Float)
    bid_count_3: Mapped[int | None] = mapped_column(Integer)
    bid_volume_3: Mapped[int | None] = mapped_column(BigInteger)
    bid_price_3: Mapped[float | None] = mapped_column(Float)
    bid_count_4: Mapped[int | None] = mapped_column(Integer)
    bid_volume_4: Mapped[int | None] = mapped_column(BigInteger)
    bid_price_4: Mapped[float | None] = mapped_column(Float)
    bid_count_5: Mapped[int | None] = mapped_column(Integer)
    bid_volume_5: Mapped[int | None] = mapped_column(BigInteger)
    bid_price_5: Mapped[float | None] = mapped_column(Float)

    # Orderbook (5 levels ask)
    ask_count_1: Mapped[int | None] = mapped_column(Integer)
    ask_volume_1: Mapped[int | None] = mapped_column(BigInteger)
    ask_price_1: Mapped[float | None] = mapped_column(Float)
    ask_count_2: Mapped[int | None] = mapped_column(Integer)
    ask_volume_2: Mapped[int | None] = mapped_column(BigInteger)
    ask_price_2: Mapped[float | None] = mapped_column(Float)
    ask_count_3: Mapped[int | None] = mapped_column(Integer)
    ask_volume_3: Mapped[int | None] = mapped_column(BigInteger)
    ask_price_3: Mapped[float | None] = mapped_column(Float)
    ask_count_4: Mapped[int | None] = mapped_column(Integer)
    ask_volume_4: Mapped[int | None] = mapped_column(BigInteger)
    ask_price_4: Mapped[float | None] = mapped_column(Float)
    ask_count_5: Mapped[int | None] = mapped_column(Integer)
    ask_volume_5: Mapped[int | None] = mapped_column(BigInteger)
    ask_price_5: Mapped[float | None] = mapped_column(Float)

    # Meta
    time: Mapped[str | None] = mapped_column(String(20))
    # timestamptz in the live DB (migration 001) — match it, like IndexValueModel.
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    __table_args__ = (
        Index("idx_snap_ins_fetched", "ins_id", "fetched_at"),
        Index("idx_snap_symbol_fetched", "symbol", "fetched_at"),
        # Unique per (symbol, fetched_at) so the bulk-insert upsert
        # (INSERT ... ON CONFLICT DO NOTHING) actually deduplicates rows
        # instead of appending a new snapshot every 2-minute sync cycle.
        # Without this the table grows unboundedly and the latest-wins
        # DISTINCT ON (symbol) query in the alert/quote jobs keeps seeing
        # stale rows.
        UniqueConstraint("symbol", "fetched_at", name="uq_snap_symbol_fetched"),
    )


class SymbolDetailModel(InstrumentRefMixin, BrsApiBase):
    """
    Enriched symbol detail from ``Symbol.php`` endpoint.

    One row per symbol (latest version kept / upserted on fetch).
    """

    __tablename__ = "brsapi_symbol_details"

    ins_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    instrument_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True, comment="FK to instruments.id")
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    name_en: Mapped[str | None] = mapped_column(String(200))
    isin: Mapped[str | None] = mapped_column(String(50), index=True)
    code_12: Mapped[str | None] = mapped_column(String(20))
    code_5: Mapped[str | None] = mapped_column(String(20))
    code_4: Mapped[str | None] = mapped_column(String(20))
    market: Mapped[str | None] = mapped_column(String(30))
    board: Mapped[str | None] = mapped_column(String(50))
    board_id: Mapped[str | None] = mapped_column(String(20))
    board_code: Mapped[str | None] = mapped_column(String(10))
    sector: Mapped[str | None] = mapped_column(String(100))
    sector_id: Mapped[int | None] = mapped_column(Integer)
    sub_sector: Mapped[str | None] = mapped_column(String(100))
    sub_sector_id: Mapped[int | None] = mapped_column(Integer)

    shares_count: Mapped[int | None] = mapped_column(BigInteger)
    shares_issued: Mapped[int | None] = mapped_column(BigInteger)
    base_volume: Mapped[int | None] = mapped_column(BigInteger)
    market_value: Mapped[float | None] = mapped_column(Float)
    free_float_pct: Mapped[float | None] = mapped_column(Float)
    eps: Mapped[float | None] = mapped_column(Float)
    pe_ratio: Mapped[float | None] = mapped_column(Float)
    group_pe_ratio: Mapped[float | None] = mapped_column(Float)
    ps_ratio: Mapped[float | None] = mapped_column(Float)
    price_lowest_allowed: Mapped[float | None] = mapped_column(Float, comment="tmin — آستانه مجاز پایین")
    price_highest_allowed: Mapped[float | None] = mapped_column(Float, comment="tmax — آستانه مجاز بالا")

    price_min_week: Mapped[float | None] = mapped_column(Float)
    price_max_week: Mapped[float | None] = mapped_column(Float)
    price_min_year: Mapped[float | None] = mapped_column(Float)
    price_max_year: Mapped[float | None] = mapped_column(Float)
    price_min: Mapped[float | None] = mapped_column(Float)
    price_max: Mapped[float | None] = mapped_column(Float)
    price_yesterday: Mapped[float | None] = mapped_column(Float)
    price_first: Mapped[float | None] = mapped_column(Float)
    price_last: Mapped[float | None] = mapped_column(Float)
    price_last_change: Mapped[float | None] = mapped_column(Float)
    price_last_change_pct: Mapped[float | None] = mapped_column(Float)
    price_close: Mapped[float | None] = mapped_column(Float)
    price_close_change: Mapped[float | None] = mapped_column(Float)
    price_close_change_pct: Mapped[float | None] = mapped_column(Float)

    trade_count: Mapped[int | None] = mapped_column(Integer)
    trade_volume: Mapped[int | None] = mapped_column(BigInteger)
    trade_volume_avg_month: Mapped[int | None] = mapped_column(BigInteger)
    trade_value: Mapped[float | None] = mapped_column(Float)

    buy_real_count: Mapped[int | None] = mapped_column(Integer)
    buy_legal_count: Mapped[int | None] = mapped_column(Integer)
    sell_real_count: Mapped[int | None] = mapped_column(Integer)
    sell_legal_count: Mapped[int | None] = mapped_column(Integer)
    buy_real_volume: Mapped[int | None] = mapped_column(BigInteger)
    buy_legal_volume: Mapped[int | None] = mapped_column(BigInteger)
    sell_real_volume: Mapped[int | None] = mapped_column(BigInteger)
    sell_legal_volume: Mapped[int | None] = mapped_column(BigInteger)

    state: Mapped[str | None] = mapped_column(String(20))
    date: Mapped[str | None] = mapped_column(String(20))
    date_update: Mapped[str | None] = mapped_column(String(20))
    time: Mapped[str | None] = mapped_column(String(20))

    assembly: Mapped[dict | list | None] = mapped_column(JSONB, comment="JSON array of assembly info")
    raw_json: Mapped[dict | None] = mapped_column(JSONB)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class IndexValueModel(InstrumentRefMixin, BrsApiBase):
    """
    Index value snapshots from ``Index.php``.

    Covers market indices (TSE main, equal-weight, Farabours, selected).
    """

    __tablename__ = "brsapi_index_values"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    state: Mapped[str | None] = mapped_column(String(50))
    index_value: Mapped[float | None] = mapped_column(Float)
    index_change: Mapped[float | None] = mapped_column(Float)
    index_change_pct: Mapped[float | None] = mapped_column(Float)
    index_equal_weight: Mapped[float | None] = mapped_column(Float)
    index_equal_weight_change: Mapped[float | None] = mapped_column(Float)
    market_value: Mapped[float | None] = mapped_column(Float)
    market_value_main: Mapped[float | None] = mapped_column(Float)
    market_value_base: Mapped[float | None] = mapped_column(Float)
    trade_count: Mapped[int | None] = mapped_column(Integer)
    trade_volume: Mapped[int | None] = mapped_column(BigInteger)
    trade_value: Mapped[float | None] = mapped_column(Float)
    min: Mapped[float | None] = mapped_column(Float)
    max: Mapped[float | None] = mapped_column(Float)
    date: Mapped[str | None] = mapped_column(String(20), index=True)
    time: Mapped[str | None] = mapped_column(String(20))
    # Live DB column is DateTime (created by migration 001) — keep the model in
    # sync so the parser can bind a real datetime (asyncpg rejects str here).
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime)
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_index_name_date", "name", "date"),
    )


class NavRecordModel(InstrumentRefMixin, BrsApiBase):
    """
    NAV (Net Asset Value) for ETF funds from ``Nav.php``.

    Each row represents one NAV snapshot for a symbol at a point in time.
    """

    __tablename__ = "brsapi_nav_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    nav_issue: Mapped[float | None] = mapped_column(Float, comment="NAV صدور")
    nav_redemption: Mapped[float | None] = mapped_column(Float, comment="NAV ابطال")
    date: Mapped[str | None] = mapped_column(String(20), index=True)
    time: Mapped[str | None] = mapped_column(String(20))
    fetched_at: Mapped[str | None] = mapped_column(String(30))
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_nav_symbol_date", "symbol", "date"),
    )


class OptionSnapshotModel(InstrumentRefMixin, BrsApiBase):
    """
    Option contract snapshots from ``Option.php``.

    One row per option contract per fetch cycle.
    """

    __tablename__ = "brsapi_option_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ins_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    isin: Mapped[str | None] = mapped_column(String(50))
    underlying_symbol: Mapped[str | None] = mapped_column(String(50), index=True)
    underlying_id: Mapped[str | None] = mapped_column(String(50))
    option_type: Mapped[str | None] = mapped_column(String(10), comment="call / put")
    contract_size: Mapped[int | None] = mapped_column(Integer)
    strike_price: Mapped[float | None] = mapped_column(Float)
    open_interest: Mapped[int | None] = mapped_column(Integer)
    date_begin: Mapped[str | None] = mapped_column(String(20))
    date_end: Mapped[str | None] = mapped_column(String(20), index=True)
    days_remaining: Mapped[int | None] = mapped_column(Integer)
    sector: Mapped[str | None] = mapped_column(String(100))
    sector_id: Mapped[int | None] = mapped_column(Integer)

    underlying_price_yesterday: Mapped[float | None] = mapped_column(Float)
    underlying_price_last: Mapped[float | None] = mapped_column(Float)
    underlying_price_last_change_pct: Mapped[float | None] = mapped_column(Float)
    underlying_price_close: Mapped[float | None] = mapped_column(Float)
    underlying_price_close_change_pct: Mapped[float | None] = mapped_column(Float)

    price_min: Mapped[float | None] = mapped_column(Float)
    price_max: Mapped[float | None] = mapped_column(Float)
    price_yesterday: Mapped[float | None] = mapped_column(Float)
    price_first: Mapped[float | None] = mapped_column(Float)
    price_last: Mapped[float | None] = mapped_column(Float)
    price_last_change: Mapped[float | None] = mapped_column(Float)
    price_last_change_pct: Mapped[float | None] = mapped_column(Float)
    price_close: Mapped[float | None] = mapped_column(Float)
    price_close_change: Mapped[float | None] = mapped_column(Float)
    price_close_change_pct: Mapped[float | None] = mapped_column(Float)

    trade_count: Mapped[int | None] = mapped_column(Integer)
    trade_volume: Mapped[int | None] = mapped_column(Integer)
    trade_value: Mapped[float | None] = mapped_column(Float)
    notional_value: Mapped[float | None] = mapped_column(Float)

    buy_real_count: Mapped[int | None] = mapped_column(Integer)
    buy_legal_count: Mapped[int | None] = mapped_column(Integer)
    sell_real_count: Mapped[int | None] = mapped_column(Integer)
    sell_legal_count: Mapped[int | None] = mapped_column(Integer)
    buy_real_volume: Mapped[int | None] = mapped_column(Integer)
    buy_legal_volume: Mapped[int | None] = mapped_column(Integer)
    sell_real_volume: Mapped[int | None] = mapped_column(Integer)
    sell_legal_volume: Mapped[int | None] = mapped_column(Integer)

    # Orderbook (5 levels bid)
    bid_count_1: Mapped[int | None] = mapped_column(Integer)
    bid_volume_1: Mapped[int | None] = mapped_column(Integer)
    bid_price_1: Mapped[float | None] = mapped_column(Float)
    bid_count_2: Mapped[int | None] = mapped_column(Integer)
    bid_volume_2: Mapped[int | None] = mapped_column(Integer)
    bid_price_2: Mapped[float | None] = mapped_column(Float)
    bid_count_3: Mapped[int | None] = mapped_column(Integer)
    bid_volume_3: Mapped[int | None] = mapped_column(Integer)
    bid_price_3: Mapped[float | None] = mapped_column(Float)
    bid_count_4: Mapped[int | None] = mapped_column(Integer)
    bid_volume_4: Mapped[int | None] = mapped_column(Integer)
    bid_price_4: Mapped[float | None] = mapped_column(Float)
    bid_count_5: Mapped[int | None] = mapped_column(Integer)
    bid_volume_5: Mapped[int | None] = mapped_column(Integer)
    bid_price_5: Mapped[float | None] = mapped_column(Float)

    # Orderbook (5 levels ask)
    ask_count_1: Mapped[int | None] = mapped_column(Integer)
    ask_volume_1: Mapped[int | None] = mapped_column(Integer)
    ask_price_1: Mapped[float | None] = mapped_column(Float)
    ask_count_2: Mapped[int | None] = mapped_column(Integer)
    ask_volume_2: Mapped[int | None] = mapped_column(Integer)
    ask_price_2: Mapped[float | None] = mapped_column(Float)
    ask_count_3: Mapped[int | None] = mapped_column(Integer)
    ask_volume_3: Mapped[int | None] = mapped_column(Integer)
    ask_price_3: Mapped[float | None] = mapped_column(Float)
    ask_count_4: Mapped[int | None] = mapped_column(Integer)
    ask_volume_4: Mapped[int | None] = mapped_column(Integer)
    ask_price_4: Mapped[float | None] = mapped_column(Float)
    ask_count_5: Mapped[int | None] = mapped_column(Integer)
    ask_volume_5: Mapped[int | None] = mapped_column(Integer)
    ask_price_5: Mapped[float | None] = mapped_column(Float)

    time: Mapped[str | None] = mapped_column(String(20))
    fetched_at: Mapped[str | None] = mapped_column(String(30))
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_option_underlying", "underlying_symbol", "date_end"),
        Index("idx_option_symbol_fetched", "symbol", "fetched_at"),
    )


class IntradayTradeModel(InstrumentRefMixin, BrsApiBase):
    """Intraday trade ticks from ``Transaction.php``."""

    __tablename__ = "brsapi_intraday_trades"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    row: Mapped[int | None] = mapped_column(Integer)
    time: Mapped[str | None] = mapped_column(String(20))
    volume: Mapped[int | None] = mapped_column(Integer)
    price: Mapped[float | None] = mapped_column(Float)
    canceled: Mapped[bool | None] = mapped_column(BooleanDefaultFalse, default=False, server_default="false")
    trade_date: Mapped[str | None] = mapped_column(String(20), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_trade_symbol_date", "symbol", "trade_date"),
    )


class HistoricalDailyModel(InstrumentRefMixin, BrsApiBase):
    """
    Daily historical price data from ``History.php?type=0``.

    Partitioned by ``date`` (yearly). One row per symbol per day.
    """

    __tablename__ = "brsapi_historical_daily"

    id: Mapped[int] = mapped_column(BigInteger, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    date: Mapped[str] = mapped_column(String(20), nullable=False)
    time: Mapped[str | None] = mapped_column(String(20))
    trade_count: Mapped[int | None] = mapped_column(Integer)
    trade_volume: Mapped[int | None] = mapped_column(BigInteger)
    trade_value: Mapped[float | None] = mapped_column(Float)
    price_min: Mapped[float | None] = mapped_column(Float)
    price_max: Mapped[float | None] = mapped_column(Float)
    price_yesterday: Mapped[float | None] = mapped_column(Float)
    price_first: Mapped[float | None] = mapped_column(Float)
    price_last: Mapped[float | None] = mapped_column(Float)
    price_last_change: Mapped[float | None] = mapped_column(Float)
    price_last_change_pct: Mapped[float | None] = mapped_column(Float)
    price_close: Mapped[float | None] = mapped_column(Float)
    price_close_change: Mapped[float | None] = mapped_column(Float)
    price_close_change_pct: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        PrimaryKeyConstraint("id", "date"),
        Index("idx_hist_symbol_date", "symbol", "date"),
        Index("idx_hist_date", "date"),
        Index("idx_hist_symbol", "symbol"),
        Index("idx_hist_ins_id", "ins_id"),
        Index("idx_hist_instrument_id", "instrument_id"),
    )


class HistoricalRealLegalModel(InstrumentRefMixin, BrsApiBase):
    """
    Daily real/legal breakdown from ``History.php?type=1``.

    Partitioned by ``date`` (yearly).
    """

    __tablename__ = "brsapi_historical_real_legal"

    id: Mapped[int] = mapped_column(BigInteger, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    date: Mapped[str] = mapped_column(String(20), nullable=False)
    buy_real_count: Mapped[int | None] = mapped_column(Integer)
    buy_legal_count: Mapped[int | None] = mapped_column(Integer)
    sell_real_count: Mapped[int | None] = mapped_column(Integer)
    sell_legal_count: Mapped[int | None] = mapped_column(Integer)
    buy_real_volume: Mapped[int | None] = mapped_column(BigInteger)
    buy_legal_volume: Mapped[int | None] = mapped_column(BigInteger)
    sell_real_volume: Mapped[int | None] = mapped_column(BigInteger)
    sell_legal_volume: Mapped[int | None] = mapped_column(BigInteger)
    buy_real_value: Mapped[float | None] = mapped_column(Float)
    buy_legal_value: Mapped[float | None] = mapped_column(Float)
    sell_real_value: Mapped[float | None] = mapped_column(Float)
    sell_legal_value: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        PrimaryKeyConstraint("id", "date"),
        Index("idx_rl_symbol_date", "symbol", "date"),
        Index("idx_rl_date", "date"),
        Index("idx_rl_symbol", "symbol"),
        Index("idx_rl_ins_id", "ins_id"),
        Index("idx_rl_instrument_id", "instrument_id"),
    )


class CandlestickModel(InstrumentRefMixin, BrsApiBase):
    """OHLCV candlestick data from ``Candlestick.php``."""

    __tablename__ = "brsapi_candlesticks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    date: Mapped[str] = mapped_column(String(20), nullable=False)
    time: Mapped[str | None] = mapped_column(String(20))
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[int | None] = mapped_column(BigInteger)
    count: Mapped[int | None] = mapped_column(Integer)
    candle_type: Mapped[str | None] = mapped_column(
        String(10), default="1", comment="1=realtime, 2=unadjusted, 3=adjusted"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_candle_symbol_date", "symbol", "date", "candle_type"),
    )


class ShareholderRecordModel(InstrumentRefMixin, BrsApiBase):
    """
    Shareholder composition from ``Shareholder.php``.

    One row per shareholder per symbol snapshot.
    """

    __tablename__ = "brsapi_shareholder_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    shareholder_name: Mapped[str] = mapped_column(String(200), nullable=False)
    volume: Mapped[int | None] = mapped_column(BigInteger)
    percent: Mapped[float | None] = mapped_column(Float)
    change: Mapped[int | None] = mapped_column(BigInteger)
    date: Mapped[str | None] = mapped_column(String(20), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_sh_symbol_date", "symbol", "date"),
    )
