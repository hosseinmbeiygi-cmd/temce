"""SQLAlchemy ORM models for options data.

Covers:
- Option contracts (with all market metadata)
- Option trades
- Option snapshots (daily snapshots for backtesting)
- Volatility surface data
- Corporate actions
- Open Interest history
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin


class OptionContractModel(TimestampMixin, Base):
    """Option contract definition."""
    __tablename__ = "option_contracts"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    underlying_symbol: Mapped[str] = mapped_column(String(50), index=True)
    underlying_isin: Mapped[str | None] = mapped_column(String(20))
    option_type: Mapped[str] = mapped_column(String(10))  # call, put
    strike_price: Mapped[float] = mapped_column(Float)
    expiry_date: Mapped[date] = mapped_column(Date)
    contract_size: Mapped[int] = mapped_column(Integer, default=1)
    currency: Mapped[str] = mapped_column(String(10), default="IRR")
    style: Mapped[str] = mapped_column(String(20), default="european")
    settlement_mode: Mapped[str] = mapped_column(String(20), default="cash")
    asset_class: Mapped[str] = mapped_column(String(30), default="equity")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    isin: Mapped[str | None] = mapped_column(String(20))
    market: Mapped[str] = mapped_column(String(10), default="tse")

    __table_args__ = (
        Index("idx_option_underlying_expiry", "underlying_symbol", "expiry_date"),
        Index("idx_option_type_expiry", "option_type", "expiry_date"),
    )


class OptionSnapshotModel(TimestampMixin, Base):
    """Daily snapshot of option market data."""
    __tablename__ = "option_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("option_contracts.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    open_price: Mapped[float] = mapped_column(Float, default=0)
    high_price: Mapped[float] = mapped_column(Float, default=0)
    low_price: Mapped[float] = mapped_column(Float, default=0)
    close_price: Mapped[float] = mapped_column(Float, default=0)
    settlement_price: Mapped[float | None] = mapped_column(Float)
    last_price: Mapped[float] = mapped_column(Float, default=0)
    volume: Mapped[int] = mapped_column(Integer, default=0)
    open_interest: Mapped[int] = mapped_column(Integer, default=0)
    bid_price: Mapped[float | None] = mapped_column(Float)
    ask_price: Mapped[float | None] = mapped_column(Float)
    bid_volume: Mapped[int | None] = mapped_column(Integer)
    ask_volume: Mapped[int | None] = mapped_column(Integer)
    implied_volatility: Mapped[float | None] = mapped_column(Float)
    delta: Mapped[float | None] = mapped_column(Float)
    gamma: Mapped[float | None] = mapped_column(Float)
    theta: Mapped[float | None] = mapped_column(Float)
    vega: Mapped[float | None] = mapped_column(Float)
    rho: Mapped[float | None] = mapped_column(Float)
    underlying_price: Mapped[float | None] = mapped_column(Float)
    block_volume: Mapped[int] = mapped_column(Integer, default=0)
    meta: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        UniqueConstraint("contract_id", "date", name="uq_snapshot_contract_date"),
        Index("idx_snapshot_date", "date"),
    )


class OptionTradeModel(TimestampMixin, Base):
    """Individual option trades."""
    __tablename__ = "option_trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("option_contracts.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    time: Mapped[str | None] = mapped_column(String(10))
    side: Mapped[str] = mapped_column(String(10))  # buy, sell
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Float)
    value: Mapped[float] = mapped_column(Float)
    is_block_trade: Mapped[bool] = mapped_column(Boolean, default=False)
    meta: Mapped[dict | None] = mapped_column(JSONB)


class OpenInterestHistoryModel(Base):
    """Historical open interest tracking."""
    __tablename__ = "open_interest_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("option_contracts.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    open_interest: Mapped[int] = mapped_column(Integer)
    change_oi: Mapped[int] = mapped_column(Integer, default=0)
    change_pct: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        UniqueConstraint("contract_id", "date", name="uq_oi_contract_date"),
    )


class VolatilitySurfaceModel(Base):
    """Volatility surface data point."""
    __tablename__ = "volatility_surface"

    id: Mapped[int] = mapped_column(primary_key=True)
    underlying_symbol: Mapped[str] = mapped_column(String(50), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    strike: Mapped[float] = mapped_column(Float)
    expiry_date: Mapped[date] = mapped_column(Date)
    days_to_expiry: Mapped[int] = mapped_column(Integer)
    moneyness: Mapped[float | None] = mapped_column(Float)  # K/S
    implied_volatility: Mapped[float] = mapped_column(Float)
    option_type: Mapped[str] = mapped_column(String(10))

    __table_args__ = (
        UniqueConstraint("underlying_symbol", "date", "strike", "expiry_date",
                         name="uq_surface_point"),
    )


class CorporateActionModel(Base):
    """Corporate actions affecting option contracts."""
    __tablename__ = "corporate_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    action_type: Mapped[str] = mapped_column(String(30))  # dividend, bonus, rights, split
    ex_date: Mapped[date] = mapped_column(Date, index=True)
    record_date: Mapped[date | None] = mapped_column(Date)
    params: Mapped[dict] = mapped_column(JSONB)  # e.g., {"dividend": 1500} or {"bonus_ratio": 0.2}
    applied: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(30), default="codal")
    raw_text: Mapped[str | None] = mapped_column(Text)
