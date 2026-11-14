"""Historical transaction records from TSE (Tehran Stock Exchange)."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import DateTime, Float, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class TransactionModel(Base):
    """Raw tick data for equity/fund trades on TSE.

    R10 migration: imported from transactions.db SQLite archive
    (36.4M historical trade records, 1990-2024).
    Uses TimescaleDB hypertable on trade_date for compression.
    """

    __tablename__ = "transactions"

    symbol: Mapped[str] = mapped_column(String(16), primary_key=True, index=True)
    trade_date: Mapped[date] = mapped_column(primary_key=True)
    seq_no: Mapped[int] = mapped_column(Integer, primary_key=True)
    time: Mapped[str] = mapped_column(String(8))  # HH:MM:SS
    volume: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Float)
    is_canceled: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_transactions_symbol_date", "symbol", "trade_date"),
        Index("ix_transactions_price", "price"),
    )
