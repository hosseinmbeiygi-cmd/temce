"""Reference DB models for Phase 2-1: Normalizer + Reference DB.

Instruments, contracts (options/futures), and market snapshots form the
canonical reference layer that all 5 data sources (IME/TSETMC) normalise into.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class ContractModel(TimestampMixin, Base):
    """Derivative/commodity contract (option, future, physical delivery)."""

    __tablename__ = "contracts"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(String(50), ForeignKey("instruments.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    asset_class: Mapped[str | None] = mapped_column(String(20), index=True)  # equity/commodity/certificate
    contract_type: Mapped[str | None] = mapped_column(String(20), index=True)  # call/put/future/physical
    expiry: Mapped[date | None] = mapped_column(Date, index=True)
    strike: Mapped[float | None] = mapped_column(Numeric(18, 4))
    lot_size: Mapped[int | None] = mapped_column(Integer, server_default="1000")
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True)


class MarketSnapshotModel(TimestampMixin, Base):
    """Single snapshot of market data at a point in time (reference layer)."""

    __tablename__ = "market_snapshots"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    contract_id: Mapped[str] = mapped_column(String(50), ForeignKey("contracts.id"), nullable=False, index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    price: Mapped[float | None] = mapped_column(Numeric(18, 4))
    volume: Mapped[int | None] = mapped_column(BigInteger)
    oi: Mapped[int | None] = mapped_column(BigInteger)  # open interest
    bid: Mapped[float | None] = mapped_column(Numeric(18, 4))
    ask: Mapped[float | None] = mapped_column(Numeric(18, 4))
    bid_volume: Mapped[int | None] = mapped_column(BigInteger)
    ask_volume: Mapped[int | None] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # ime/tsetmc
    quality_score: Mapped[float | None] = mapped_column(Float, default=1.0)

    __table_args__ = (Index("ix_market_snapshot_contract_ts", "contract_id", "ts"),)
