"""
Global commodity price ORM model.

Stores prices from the ``/Market/Commodity.php`` endpoint.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from brsapi.models.base import BrsApiBase, InstrumentRefMixin


class GoldCoinPriceModel(InstrumentRefMixin, BrsApiBase):
    """
    Gold & coin prices from ``/Market/Coin.php``.

    One row per gold/coin item per fetch (e.g. gold18, gold24, coin, etc.).
    """

    __tablename__ = "brsapi_gold_coin_prices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(100))
    price: Mapped[float | None] = mapped_column(Float)
    change_value: Mapped[float | None] = mapped_column(Float)
    change_percent: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(20), default="IRR")
    date: Mapped[str | None] = mapped_column(String(20))
    time: Mapped[str | None] = mapped_column(String(20))
    time_unix: Mapped[int | None] = mapped_column(BigInteger)
    fetched_at: Mapped[str | None] = mapped_column(String(30))
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_gold_symbol_fetched", "symbol", "fetched_at"),
    )


class GoldCoinHistoryModel(InstrumentRefMixin, BrsApiBase):
    """
    Historical gold & coin prices from ``/Market/CoinHistory.php``.
    """

    __tablename__ = "brsapi_gold_coin_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    date: Mapped[str] = mapped_column(String(20), nullable=False)
    price_open: Mapped[float | None] = mapped_column(Float)
    price_high: Mapped[float | None] = mapped_column(Float)
    price_low: Mapped[float | None] = mapped_column(Float)
    price_close: Mapped[float | None] = mapped_column(Float)
    fetched_at: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_gold_hist_symbol_date", "symbol", "date"),
    )


class CurrencyPriceModel(InstrumentRefMixin, BrsApiBase):
    """
    Currency/forex prices from ``/Market/Currency.php``.

    One row per currency per fetch (USD, EUR, GBP, AED, etc.).
    """

    __tablename__ = "brsapi_currency_prices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(100))
    price: Mapped[float | None] = mapped_column(Float)
    change_value: Mapped[float | None] = mapped_column(Float)
    change_percent: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(20), default="IRR")
    date: Mapped[str | None] = mapped_column(String(20))
    time: Mapped[str | None] = mapped_column(String(20))
    time_unix: Mapped[int | None] = mapped_column(BigInteger)
    fetched_at: Mapped[str | None] = mapped_column(String(30))
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_currency_symbol_fetched", "symbol", "fetched_at"),
    )


class Currency24hModel(InstrumentRefMixin, BrsApiBase):
    """
    24-hour currency change data from ``/Market/Currency24h.php``.
    """

    __tablename__ = "brsapi_currency_24h"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(100))
    price_now: Mapped[float | None] = mapped_column(Float)
    price_24h_ago: Mapped[float | None] = mapped_column(Float)
    change_value: Mapped[float | None] = mapped_column(Float)
    change_percent: Mapped[float | None] = mapped_column(Float)
    high_24h: Mapped[float | None] = mapped_column(Float)
    low_24h: Mapped[float | None] = mapped_column(Float)
    date: Mapped[str | None] = mapped_column(String(20))
    time: Mapped[str | None] = mapped_column(String(20))
    fetched_at: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_currency_24h_symbol", "symbol"),
    )


class Gold24hModel(InstrumentRefMixin, BrsApiBase):
    """
    24-hour gold price change data from ``/Market/Gold24h.php``.
    """

    __tablename__ = "brsapi_gold_24h"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(100))
    price_now: Mapped[float | None] = mapped_column(Float)
    price_24h_ago: Mapped[float | None] = mapped_column(Float)
    change_value: Mapped[float | None] = mapped_column(Float)
    change_percent: Mapped[float | None] = mapped_column(Float)
    high_24h: Mapped[float | None] = mapped_column(Float)
    low_24h: Mapped[float | None] = mapped_column(Float)
    date: Mapped[str | None] = mapped_column(String(20))
    time: Mapped[str | None] = mapped_column(String(20))
    fetched_at: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_gold_24h_symbol", "symbol"),
    )


class GoldCurrencyProPriceModel(InstrumentRefMixin, BrsApiBase):
    """
    Gold & Currency Pro real-time prices from ``/Market/Gold_Currency_Pro.php?section=...``.

    Stores gold, currency, and cryptocurrency prices with Pro-specific fields:
    ``sign``, ``url_base_icon``, ``path_icon``.
    The ``section`` column indicates which category each row belongs to.
    """

    __tablename__ = "brsapi_gold_currency_pro_prices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    section: Mapped[str] = mapped_column(String(20), nullable=False, index=True, comment="gold | currency | cryptocurrency")
    symbol: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    name_en: Mapped[str | None] = mapped_column(String(100), comment="English name")
    name: Mapped[str | None] = mapped_column(String(100), comment="Persian name")
    sign: Mapped[str | None] = mapped_column(String(10), comment="Graphical symbol like $, €")
    price: Mapped[float | None] = mapped_column(Float)
    change_value: Mapped[float | None] = mapped_column(Float)
    change_percent: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(20), default="IRR")
    url_base_icon: Mapped[str | None] = mapped_column(String(300), comment="Base URL for icons")
    path_icon: Mapped[str | None] = mapped_column(String(100), comment="Icon filename")
    date: Mapped[str | None] = mapped_column(String(20))
    time: Mapped[str | None] = mapped_column(String(20))
    time_unix: Mapped[int | None] = mapped_column(BigInteger)
    fetched_at: Mapped[str | None] = mapped_column(String(30))
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_pro_price_section_symbol", "section", "symbol"),
        Index("idx_pro_price_fetched", "fetched_at"),
    )


class GoldCurrencyProHistory24hModel(InstrumentRefMixin, BrsApiBase):
    """
    24-hour price history from ``/Market/Gold_Currency_Pro.php?history=1&symbol=XYZ``.

    One row per tick/price point in the last 24 hours for a given symbol.
    """

    __tablename__ = "brsapi_gold_currency_pro_history_24h"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    price: Mapped[float | None] = mapped_column(Float)
    time: Mapped[str | None] = mapped_column(String(20))
    date: Mapped[str | None] = mapped_column(String(20))
    time_unix: Mapped[int | None] = mapped_column(BigInteger)
    fetched_at: Mapped[str | None] = mapped_column(String(30))
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_pro_24h_symbol_date", "symbol", "date"),
        Index("idx_pro_24h_fetched", "fetched_at"),
    )


class GoldCurrencyProDailyHistoryModel(InstrumentRefMixin, BrsApiBase):
    """
    Daily OHLC history from ``/Market/Gold_Currency_Pro.php?history=2&symbol=XYZ&date_start=...&date_end=...``.

    One row per day per symbol with open, high, low, close prices.
    Dates are in Shamsi (Persian) format: YYYY-MM-DD.
    """

    __tablename__ = "brsapi_gold_currency_pro_daily_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(100))
    sign: Mapped[str | None] = mapped_column(String(10))
    unit: Mapped[str | None] = mapped_column(String(20), default="IRR")
    url_base_icon: Mapped[str | None] = mapped_column(String(300))
    path_icon: Mapped[str | None] = mapped_column(String(100))
    date: Mapped[str] = mapped_column(String(20), nullable=False)
    price_open: Mapped[float | None] = mapped_column(Float)
    price_high: Mapped[float | None] = mapped_column(Float)
    price_low: Mapped[float | None] = mapped_column(Float)
    price_close: Mapped[float | None] = mapped_column(Float)
    fetched_at: Mapped[str | None] = mapped_column(String(30))
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_pro_daily_symbol_date", "symbol", "date"),
        Index("idx_pro_daily_fetched", "fetched_at"),
    )


class CommodityPriceModel(InstrumentRefMixin, BrsApiBase):
    """
    Global commodity prices (precious metals, base metals, energy).

    One row per commodity per fetch.
    """

    __tablename__ = "brsapi_commodity_prices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(100))
    price: Mapped[float | None] = mapped_column(Float)
    change_value: Mapped[float | None] = mapped_column(Float)
    change_percent: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(20), default="USD")
    category: Mapped[str | None] = mapped_column(
        String(20), index=True, comment="precious_metal | base_metal | energy | other"
    )
    date: Mapped[str | None] = mapped_column(String(20))
    time: Mapped[str | None] = mapped_column(String(20))
    time_unix: Mapped[int | None] = mapped_column(BigInteger)
    fetched_at: Mapped[str | None] = mapped_column(String(30))
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_commodity_symbol_fetched", "symbol", "fetched_at"),
        Index("idx_commodity_cat_fetched", "category", "fetched_at"),
    )
