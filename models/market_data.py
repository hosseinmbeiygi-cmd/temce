"""SQLAlchemy ORM models for market data tables NOT already defined elsewhere.

Tables already modeled in separate files (DO NOT re-define here):
  - instruments  → models/instrument.py  (InstrumentModel)
  - trades       → models/trade.py       (TradeModel)
  - quotes       → models/quote.py       (QuoteModel)
  - codal_reports → models/codal.py      (CodalReportModel)
"""
from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, Numeric, String, Text, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


# ═══════════════════════════════════════════════════════════
# 2. symbols
# ═══════════════════════════════════════════════════════════
class SymbolModel(Base):
    __tablename__ = "symbols"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    isin: Mapped[str | None] = mapped_column(String(50))
    market_type: Mapped[str | None] = mapped_column(String(20))
    asset_class: Mapped[str | None] = mapped_column(String(20))
    industry: Mapped[str | None] = mapped_column(String(100))
    industry_id: Mapped[int | None] = mapped_column(Integer)
    total_shares: Mapped[int | None] = mapped_column(BigInteger)
    base_volume: Mapped[int | None] = mapped_column(BigInteger)
    eps: Mapped[float | None] = mapped_column(Numeric)
    pe: Mapped[float | None] = mapped_column(Numeric)
    tick_size: Mapped[float | None] = mapped_column(Numeric)
    lot_size: Mapped[int | None] = mapped_column(Integer, server_default="1")
    is_active: Mapped[bool | None] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ═══════════════════════════════════════════════════════════
# 5. daily_history
# ═══════════════════════════════════════════════════════════
class DailyHistoryModel(Base):
    __tablename__ = "daily_history"

    symbol_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    trade_count: Mapped[int | None] = mapped_column(Integer)
    trade_volume: Mapped[int | None] = mapped_column(BigInteger)
    trade_value: Mapped[float | None] = mapped_column(Numeric)
    price_min: Mapped[float | None] = mapped_column(Numeric)
    price_max: Mapped[float | None] = mapped_column(Numeric)
    price_yesterday: Mapped[float | None] = mapped_column(Numeric)
    price_first: Mapped[float | None] = mapped_column(Numeric)
    price_last: Mapped[float | None] = mapped_column(Numeric)
    price_last_change: Mapped[float | None] = mapped_column(Numeric)
    price_last_change_pct: Mapped[float | None] = mapped_column(Numeric)
    price_close: Mapped[float | None] = mapped_column(Numeric)
    price_close_change: Mapped[float | None] = mapped_column(Numeric)
    price_close_change_pct: Mapped[float | None] = mapped_column(Numeric)


# ═══════════════════════════════════════════════════════════
# 6. intraday_trades
# ═══════════════════════════════════════════════════════════
class IntradayTradeModel(Base):
    __tablename__ = "intraday_trades"

    # PK matches migration 0001: (symbol_id, trade_date, seq_no); `time` is a
    # plain sa.Time column (NOT part of the PK) exactly like the migration DDL.
    symbol_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    seq_no: Mapped[int] = mapped_column(Integer, primary_key=True)
    time: Mapped[time] = mapped_column(Time, nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Numeric, nullable=False)
    is_canceled: Mapped[bool | None] = mapped_column(Boolean, server_default="false")


# ═══════════════════════════════════════════════════════════
# 8. shareholders
# ═══════════════════════════════════════════════════════════
class ShareholderModel(Base):
    __tablename__ = "shareholders"

    symbol_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    record_date: Mapped[date] = mapped_column(Date, primary_key=True)
    holder_name: Mapped[str] = mapped_column(String(200), primary_key=True)
    volume: Mapped[int | None] = mapped_column(BigInteger)
    percent: Mapped[float | None] = mapped_column(Numeric)
    change: Mapped[float | None] = mapped_column(Numeric)


# ═══════════════════════════════════════════════════════════
# 9. gold_currency_prices
# ═══════════════════════════════════════════════════════════
class GoldCurrencyPriceModel(Base):
    __tablename__ = "gold_currency_prices"

    symbol: Mapped[str] = mapped_column(String(30), primary_key=True)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(100))
    name_en: Mapped[str | None] = mapped_column(String(100))
    sign: Mapped[str | None] = mapped_column(String(20))
    price: Mapped[float | None] = mapped_column(Numeric)
    change_value: Mapped[float | None] = mapped_column(Numeric)
    change_pct: Mapped[float | None] = mapped_column(Numeric)
    unit: Mapped[str | None] = mapped_column(String(20))
    section: Mapped[str | None] = mapped_column(String(20))


# ═══════════════════════════════════════════════════════════
# 10. commodity_trades
# ═══════════════════════════════════════════════════════════
class CommodityTradeModel(Base):
    __tablename__ = "commodity_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str | None] = mapped_column(String(50), index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    trade_date: Mapped[date | None] = mapped_column(Date)
    price: Mapped[float | None] = mapped_column(Numeric)
    volume: Mapped[float | None] = mapped_column(Numeric)
    value: Mapped[float | None] = mapped_column(Numeric)
    counter_party: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ═══════════════════════════════════════════════════════════
# 11. commodity_futures
# ═══════════════════════════════════════════════════════════
class CommodityFuturesModel(Base):
    __tablename__ = "commodity_futures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str | None] = mapped_column(String(50), index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    expiry_date: Mapped[date | None] = mapped_column(Date)
    price_last: Mapped[float | None] = mapped_column(Numeric)
    price_close: Mapped[float | None] = mapped_column(Numeric)
    trade_count: Mapped[int | None] = mapped_column(Integer)
    trade_volume: Mapped[int | None] = mapped_column(BigInteger)
    time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ═══════════════════════════════════════════════════════════
# 12. commodity_certificates
# ═══════════════════════════════════════════════════════════
class CommodityCertificateModel(Base):
    __tablename__ = "commodity_certificates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str | None] = mapped_column(String(50), index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    price: Mapped[float | None] = mapped_column(Numeric)
    volume: Mapped[int | None] = mapped_column(BigInteger)
    time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ═══════════════════════════════════════════════════════════
# 13. commodity_prices
# ═══════════════════════════════════════════════════════════
class CommodityGlobalPriceModel(Base):
    __tablename__ = "commodity_prices"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(100))
    price: Mapped[float | None] = mapped_column(Numeric)
    change_value: Mapped[float | None] = mapped_column(Numeric)
    change_pct: Mapped[float | None] = mapped_column(Numeric)
    unit: Mapped[str | None] = mapped_column(String(20))


# ═══════════════════════════════════════════════════════════
# 14. commodity_funds
# ═══════════════════════════════════════════════════════════
class CommodityFundModel(Base):
    __tablename__ = "commodity_funds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str | None] = mapped_column(String(50), index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    nav: Mapped[float | None] = mapped_column(Numeric)
    price: Mapped[float | None] = mapped_column(Numeric)
    time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ═══════════════════════════════════════════════════════════
# 15. commodity_options
# ═══════════════════════════════════════════════════════════
class CommodityOptionModel(Base):
    __tablename__ = "commodity_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str | None] = mapped_column(String(50), index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    underlying: Mapped[str | None] = mapped_column(String(50))
    strike_price: Mapped[float | None] = mapped_column(Numeric)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    option_type: Mapped[str | None] = mapped_column(String(10))
    price_last: Mapped[float | None] = mapped_column(Numeric)
    time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ═══════════════════════════════════════════════════════════
# 16. indices
# ═══════════════════════════════════════════════════════════
class IndexModel(Base):
    __tablename__ = "indices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(200))
    value: Mapped[float | None] = mapped_column(Numeric)
    change_value: Mapped[float | None] = mapped_column(Numeric)
    change_pct: Mapped[float | None] = mapped_column(Numeric)
    time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ═══════════════════════════════════════════════════════════
# 17. options
# ═══════════════════════════════════════════════════════════
class StockOptionModel(Base):
    __tablename__ = "options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str | None] = mapped_column(String(50), index=True)
    underlying_symbol: Mapped[str | None] = mapped_column(String(20))
    strike_price: Mapped[float | None] = mapped_column(Numeric)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    option_type: Mapped[str | None] = mapped_column(String(10))
    price_last: Mapped[float | None] = mapped_column(Numeric)
    price_close: Mapped[float | None] = mapped_column(Numeric)
    trade_count: Mapped[int | None] = mapped_column(Integer)
    trade_volume: Mapped[int | None] = mapped_column(BigInteger)
    time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ═══════════════════════════════════════════════════════════
# 18. etf_nav
# ═══════════════════════════════════════════════════════════
class EtfNavModel(Base):
    __tablename__ = "etf_nav"

    symbol_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    nav: Mapped[float | None] = mapped_column(Numeric)
    price: Mapped[float | None] = mapped_column(Numeric)
    discount_premium: Mapped[float | None] = mapped_column(Numeric)


# ═══════════════════════════════════════════════════════════
# 19. daily_real_legal
# ═══════════════════════════════════════════════════════════
class DailyRealLegalModel(Base):
    __tablename__ = "daily_real_legal"

    symbol_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    real_buy_count: Mapped[int | None] = mapped_column(Integer)
    real_sell_count: Mapped[int | None] = mapped_column(Integer)
    legal_buy_count: Mapped[int | None] = mapped_column(Integer)
    legal_sell_count: Mapped[int | None] = mapped_column(Integer)
    real_buy_volume: Mapped[int | None] = mapped_column(BigInteger)
    real_sell_volume: Mapped[int | None] = mapped_column(BigInteger)
    legal_buy_volume: Mapped[int | None] = mapped_column(BigInteger)
    legal_sell_volume: Mapped[int | None] = mapped_column(BigInteger)
    real_buy_value: Mapped[float | None] = mapped_column(Numeric)
    real_sell_value: Mapped[float | None] = mapped_column(Numeric)
    legal_buy_value: Mapped[float | None] = mapped_column(Numeric)
    legal_sell_value: Mapped[float | None] = mapped_column(Numeric)
