"""
IME (Iran Mercantile Exchange) ORM models.

Each model stores data from one BrsApi IME endpoint.
All tables use the ``brsapi_ime_`` prefix.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from brsapi.models.base import BrsApiBase, InstrumentRefMixin


class ImeFutureModel(InstrumentRefMixin, BrsApiBase):
    """Futures contracts from ``/IME/Futures.php``."""

    __tablename__ = "brsapi_ime_futures"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    contract_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    contract_description: Mapped[str | None] = mapped_column(String(300))
    contract_size: Mapped[int | None] = mapped_column(Integer)
    contract_size_unit: Mapped[str | None] = mapped_column(String(50))
    contract_currency: Mapped[str | None] = mapped_column(String(10))

    date_end: Mapped[str | None] = mapped_column(String(20), index=True)
    date_end_text: Mapped[str | None] = mapped_column(String(50))
    days_remaining: Mapped[int | None] = mapped_column(Integer)
    margin_initial: Mapped[float | None] = mapped_column(Float)
    margin_maintenance: Mapped[float | None] = mapped_column(Float)
    open_interest: Mapped[int | None] = mapped_column(Integer)
    open_interest_change: Mapped[int | None] = mapped_column(Integer)
    open_interest_change_pct: Mapped[float | None] = mapped_column(Float)

    price_yesterday: Mapped[float | None] = mapped_column(Float)
    price_first: Mapped[float | None] = mapped_column(Float)
    price_first_change: Mapped[float | None] = mapped_column(Float)
    price_first_change_pct: Mapped[float | None] = mapped_column(Float)
    price_max: Mapped[float | None] = mapped_column(Float)
    price_max_change: Mapped[float | None] = mapped_column(Float)
    price_max_change_pct: Mapped[float | None] = mapped_column(Float)
    price_min: Mapped[float | None] = mapped_column(Float)
    price_min_change: Mapped[float | None] = mapped_column(Float)
    price_min_change_pct: Mapped[float | None] = mapped_column(Float)
    price_last: Mapped[float | None] = mapped_column(Float)
    price_last_change: Mapped[float | None] = mapped_column(Float)
    price_last_change_pct: Mapped[float | None] = mapped_column(Float)
    price_last_settlement: Mapped[float | None] = mapped_column(Float)

    trade_count: Mapped[int | None] = mapped_column(Integer)
    trade_volume: Mapped[int | None] = mapped_column(Integer)
    trade_value: Mapped[float | None] = mapped_column(Float)
    trade_value_unit: Mapped[str | None] = mapped_column(String(20))

    buy_real_count: Mapped[int | None] = mapped_column(Integer)
    buy_legal_count: Mapped[int | None] = mapped_column(Integer)
    sell_real_count: Mapped[int | None] = mapped_column(Integer)
    sell_legal_count: Mapped[int | None] = mapped_column(Integer)

    # Orderbook (3 levels bid)
    bid_volume_1: Mapped[int | None] = mapped_column(Integer)
    bid_price_1: Mapped[float | None] = mapped_column(Float)
    bid_volume_2: Mapped[int | None] = mapped_column(Integer)
    bid_price_2: Mapped[float | None] = mapped_column(Float)
    bid_volume_3: Mapped[int | None] = mapped_column(Integer)
    bid_price_3: Mapped[float | None] = mapped_column(Float)

    # Orderbook (3 levels ask)
    ask_volume_1: Mapped[int | None] = mapped_column(Integer)
    ask_price_1: Mapped[float | None] = mapped_column(Float)
    ask_volume_2: Mapped[int | None] = mapped_column(Integer)
    ask_price_2: Mapped[float | None] = mapped_column(Float)
    ask_volume_3: Mapped[int | None] = mapped_column(Integer)
    ask_price_3: Mapped[float | None] = mapped_column(Float)

    time: Mapped[str | None] = mapped_column(String(20))
    date_update: Mapped[str | None] = mapped_column(String(20))
    time_update: Mapped[str | None] = mapped_column(String(20))
    fetched_at: Mapped[str | None] = mapped_column(String(30))
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_ime_futures_code_date", "contract_code", "date_update"),
    )


class ImeOptionModel(InstrumentRefMixin, BrsApiBase):
    """Option contracts from ``/IME/Option.php``."""

    __tablename__ = "brsapi_ime_options"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    contract_category: Mapped[str | None] = mapped_column(String(100))
    contract_category_sub: Mapped[str | None] = mapped_column(String(50))
    contract_category_commodity: Mapped[str | None] = mapped_column(String(50))
    strike_price: Mapped[float | None] = mapped_column(Float)
    level_strike: Mapped[str | None] = mapped_column(String(10))

    # Call
    call_contract_id: Mapped[int | None] = mapped_column(BigInteger)
    call_contract_code: Mapped[str | None] = mapped_column(String(50), index=True)
    call_contract_description: Mapped[str | None] = mapped_column(String(300))
    call_contract_size: Mapped[int | None] = mapped_column(Integer)
    call_contract_size_unit: Mapped[str | None] = mapped_column(String(50))
    call_contract_currency: Mapped[str | None] = mapped_column(String(10))
    call_date_end: Mapped[str | None] = mapped_column(String(20))
    call_days_remaining: Mapped[int | None] = mapped_column(Integer)
    call_margin_initial: Mapped[float | None] = mapped_column(Float)
    call_margin_required: Mapped[float | None] = mapped_column(Float)
    call_open_interest: Mapped[int | None] = mapped_column(Integer)
    call_open_interest_change: Mapped[int | None] = mapped_column(Integer)
    call_open_interest_change_pct: Mapped[float | None] = mapped_column(Float)
    call_price_yesterday: Mapped[float | None] = mapped_column(Float)
    call_price_first: Mapped[float | None] = mapped_column(Float)
    call_price_first_change: Mapped[float | None] = mapped_column(Float)
    call_price_first_change_pct: Mapped[float | None] = mapped_column(Float)
    call_price_max: Mapped[float | None] = mapped_column(Float)
    call_price_max_change: Mapped[float | None] = mapped_column(Float)
    call_price_max_change_pct: Mapped[float | None] = mapped_column(Float)
    call_price_min: Mapped[float | None] = mapped_column(Float)
    call_price_min_change: Mapped[float | None] = mapped_column(Float)
    call_price_min_change_pct: Mapped[float | None] = mapped_column(Float)
    call_price_last: Mapped[float | None] = mapped_column(Float)
    call_price_last_change: Mapped[float | None] = mapped_column(Float)
    call_price_last_change_pct: Mapped[float | None] = mapped_column(Float)
    call_trade_count: Mapped[int | None] = mapped_column(Integer)
    call_trade_volume: Mapped[int | None] = mapped_column(Integer)
    call_trade_value: Mapped[float | None] = mapped_column(Float)
    call_trade_value_unit: Mapped[str | None] = mapped_column(String(20))

    # Put
    put_contract_id: Mapped[int | None] = mapped_column(BigInteger)
    put_contract_code: Mapped[str | None] = mapped_column(String(50), index=True)
    put_contract_description: Mapped[str | None] = mapped_column(String(300))
    put_contract_size: Mapped[int | None] = mapped_column(Integer)
    put_contract_size_unit: Mapped[str | None] = mapped_column(String(50))
    put_contract_currency: Mapped[str | None] = mapped_column(String(10))
    put_date_end: Mapped[str | None] = mapped_column(String(20))
    put_days_remaining: Mapped[int | None] = mapped_column(Integer)
    put_margin_initial: Mapped[float | None] = mapped_column(Float)
    put_margin_required: Mapped[float | None] = mapped_column(Float)
    put_open_interest: Mapped[int | None] = mapped_column(Integer)
    put_open_interest_change: Mapped[int | None] = mapped_column(Integer)
    put_open_interest_change_pct: Mapped[float | None] = mapped_column(Float)
    put_price_yesterday: Mapped[float | None] = mapped_column(Float)
    put_price_first: Mapped[float | None] = mapped_column(Float)
    put_price_first_change: Mapped[float | None] = mapped_column(Float)
    put_price_first_change_pct: Mapped[float | None] = mapped_column(Float)
    put_price_max: Mapped[float | None] = mapped_column(Float)
    put_price_max_change: Mapped[float | None] = mapped_column(Float)
    put_price_max_change_pct: Mapped[float | None] = mapped_column(Float)
    put_price_min: Mapped[float | None] = mapped_column(Float)
    put_price_min_change: Mapped[float | None] = mapped_column(Float)
    put_price_min_change_pct: Mapped[float | None] = mapped_column(Float)
    put_price_last: Mapped[float | None] = mapped_column(Float)
    put_price_last_change: Mapped[float | None] = mapped_column(Float)
    put_price_last_change_pct: Mapped[float | None] = mapped_column(Float)
    put_trade_count: Mapped[int | None] = mapped_column(Integer)
    put_trade_volume: Mapped[int | None] = mapped_column(Integer)
    put_trade_value: Mapped[float | None] = mapped_column(Float)
    put_trade_value_unit: Mapped[str | None] = mapped_column(String(20))

    # Call orderbook (3 levels)
    call_bid_volume_1: Mapped[int | None] = mapped_column(Integer)
    call_bid_price_1: Mapped[float | None] = mapped_column(Float)
    call_bid_volume_2: Mapped[int | None] = mapped_column(Integer)
    call_bid_price_2: Mapped[float | None] = mapped_column(Float)
    call_bid_volume_3: Mapped[int | None] = mapped_column(Integer)
    call_bid_price_3: Mapped[float | None] = mapped_column(Float)
    call_ask_volume_1: Mapped[int | None] = mapped_column(Integer)
    call_ask_price_1: Mapped[float | None] = mapped_column(Float)
    call_ask_volume_2: Mapped[int | None] = mapped_column(Integer)
    call_ask_price_2: Mapped[float | None] = mapped_column(Float)
    call_ask_volume_3: Mapped[int | None] = mapped_column(Integer)
    call_ask_price_3: Mapped[float | None] = mapped_column(Float)

    # Put orderbook (3 levels)
    put_bid_volume_1: Mapped[int | None] = mapped_column(Integer)
    put_bid_price_1: Mapped[float | None] = mapped_column(Float)
    put_bid_volume_2: Mapped[int | None] = mapped_column(Integer)
    put_bid_price_2: Mapped[float | None] = mapped_column(Float)
    put_bid_volume_3: Mapped[int | None] = mapped_column(Integer)
    put_bid_price_3: Mapped[float | None] = mapped_column(Float)
    put_ask_volume_1: Mapped[int | None] = mapped_column(Integer)
    put_ask_price_1: Mapped[float | None] = mapped_column(Float)
    put_ask_volume_2: Mapped[int | None] = mapped_column(Integer)
    put_ask_price_2: Mapped[float | None] = mapped_column(Float)
    put_ask_volume_3: Mapped[int | None] = mapped_column(Integer)
    put_ask_price_3: Mapped[float | None] = mapped_column(Float)

    time: Mapped[str | None] = mapped_column(String(20))
    date_update: Mapped[str | None] = mapped_column(String(20))
    time_update: Mapped[str | None] = mapped_column(String(20))
    fetched_at: Mapped[str | None] = mapped_column(String(30))
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_ime_option_call_code", "call_contract_code"),
        Index("idx_ime_option_put_code", "put_contract_code"),
    )


class ImeCertificateModel(InstrumentRefMixin, BrsApiBase):
    """Certificate/depository receipts from ``/IME/Certificate.php``."""

    __tablename__ = "brsapi_ime_certificates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    commodity: Mapped[str | None] = mapped_column(String(100))
    contract_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    contract_description: Mapped[str | None] = mapped_column(String(300))
    contract_size: Mapped[int | None] = mapped_column(Integer)
    contract_size_unit: Mapped[str | None] = mapped_column(String(50))
    contract_currency: Mapped[str | None] = mapped_column(String(10))

    price_yesterday: Mapped[float | None] = mapped_column(Float)
    price_first: Mapped[float | None] = mapped_column(Float)
    price_first_change: Mapped[float | None] = mapped_column(Float)
    price_first_change_pct: Mapped[float | None] = mapped_column(Float)
    price_max: Mapped[float | None] = mapped_column(Float)
    price_max_change: Mapped[float | None] = mapped_column(Float)
    price_max_change_pct: Mapped[float | None] = mapped_column(Float)
    price_min: Mapped[float | None] = mapped_column(Float)
    price_min_change: Mapped[float | None] = mapped_column(Float)
    price_min_change_pct: Mapped[float | None] = mapped_column(Float)
    price_last: Mapped[float | None] = mapped_column(Float)
    price_last_change: Mapped[float | None] = mapped_column(Float)
    price_last_change_pct: Mapped[float | None] = mapped_column(Float)

    trade_count: Mapped[int | None] = mapped_column(Integer)
    trade_volume: Mapped[int | None] = mapped_column(Integer)
    trade_value: Mapped[float | None] = mapped_column(Float)
    trade_value_unit: Mapped[str | None] = mapped_column(String(20))

    date_y: Mapped[str | None] = mapped_column(String(20))

    # Orderbook (3 levels bid)
    bid_volume_1: Mapped[int | None] = mapped_column(Integer)
    bid_price_1: Mapped[float | None] = mapped_column(Float)
    bid_volume_2: Mapped[int | None] = mapped_column(Integer)
    bid_price_2: Mapped[float | None] = mapped_column(Float)
    bid_volume_3: Mapped[int | None] = mapped_column(Integer)
    bid_price_3: Mapped[float | None] = mapped_column(Float)

    # Orderbook (3 levels ask)
    ask_volume_1: Mapped[int | None] = mapped_column(Integer)
    ask_price_1: Mapped[float | None] = mapped_column(Float)
    ask_volume_2: Mapped[int | None] = mapped_column(Integer)
    ask_price_2: Mapped[float | None] = mapped_column(Float)
    ask_volume_3: Mapped[int | None] = mapped_column(Integer)
    ask_price_3: Mapped[float | None] = mapped_column(Float)

    time: Mapped[str | None] = mapped_column(String(20))
    date_update: Mapped[str | None] = mapped_column(String(20))
    time_update: Mapped[str | None] = mapped_column(String(20))
    fetched_at: Mapped[str | None] = mapped_column(String(30))
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ImeFundModel(InstrumentRefMixin, BrsApiBase):
    """Commodity fund snapshots from ``/IME/Fund.php``."""

    __tablename__ = "brsapi_ime_funds"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ins_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    isin: Mapped[str | None] = mapped_column(String(50))

    shares_count: Mapped[int | None] = mapped_column(BigInteger)
    base_volume: Mapped[int | None] = mapped_column(BigInteger)
    market_value: Mapped[float | None] = mapped_column(Float)

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
    trade_value: Mapped[float | None] = mapped_column(Float)

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

    time: Mapped[str | None] = mapped_column(String(20))
    fetched_at: Mapped[str | None] = mapped_column(String(30))
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_ime_fund_symbol_fetched", "symbol", "fetched_at"),
    )


class ImePhysicalTradeModel(InstrumentRefMixin, BrsApiBase):
    """Physical trade records from ``/IME/Physical.php``."""

    __tablename__ = "brsapi_ime_physical_trades"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    category_id: Mapped[str | None] = mapped_column(String(50))
    offer_code: Mapped[str | None] = mapped_column(String(50))
    market_hall: Mapped[str | None] = mapped_column(String(100))
    producer: Mapped[str | None] = mapped_column(String(200))
    supplier: Mapped[str | None] = mapped_column(String(200))
    broker: Mapped[str | None] = mapped_column(String(100))
    contract_type: Mapped[str | None] = mapped_column(String(30))
    settlement_type: Mapped[str | None] = mapped_column(String(50))
    date_price_settlement: Mapped[str | None] = mapped_column(String(20))
    date_delivery: Mapped[str | None] = mapped_column(String(20))
    location_delivery: Mapped[str | None] = mapped_column(String(200))
    unit: Mapped[str | None] = mapped_column(String(30))
    packaging_type: Mapped[str | None] = mapped_column(String(50))
    currency: Mapped[str | None] = mapped_column(String(10))
    method_offer: Mapped[str | None] = mapped_column(String(30))
    method_purchase: Mapped[str | None] = mapped_column(String(30))
    date_trade: Mapped[str | None] = mapped_column(String(20), index=True)
    price_base: Mapped[float | None] = mapped_column(Float)
    volume_contract: Mapped[float | None] = mapped_column(Float)
    volume_offer: Mapped[float | None] = mapped_column(Float)
    demand: Mapped[float | None] = mapped_column(Float)
    price_min: Mapped[float | None] = mapped_column(Float)
    price_max: Mapped[float | None] = mapped_column(Float)
    price_close: Mapped[float | None] = mapped_column(Float)
    price_weighted_avg: Mapped[float | None] = mapped_column(Float)
    trade_value: Mapped[float | None] = mapped_column(Float)
    fetched_at: Mapped[str | None] = mapped_column(String(30))
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_ime_physical_trade_date", "date_trade"),
    )
