"""Paper Trading models — the signal journal + simulated trade ledger.

Three tables power the "simulate P&L from generated signals" feature:

1. ``paper_signal_snapshots`` — every signal the engine generates is saved
   here daily with ALL of its details (6 mandatory + 5 professional fields,
   scores, price, confidence, and the full JSON payload). This is the daily
   journal the user asked for.

2. ``paper_trades`` — the simulated accounting ledger. A long position is
   opened from a ``buy`` signal, and closed when a target is hit, the stop
   loss triggers, a reverse (``sell``) signal appears, or the maximum
   holding window expires. P&L is recorded per trade.

3. ``paper_equity_history`` — one row per day with the simulated account
   equity (cash + open position value + realized P&L).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class PaperSignalSnapshotModel(TimestampMixin, Base):
    """Full snapshot of every generated signal, stored once per pipeline run."""

    __tablename__ = "paper_signal_snapshots"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    # ── Core signal identity ──
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(120))
    market: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    source: Mapped[str | None] = mapped_column(String(100))

    # ── 6 mandatory + 5 professional signal fields ──
    entry_zone: Mapped[str | None] = mapped_column(Text)
    stop_loss: Mapped[str | None] = mapped_column(Text)
    targets: Mapped[str | None] = mapped_column(Text)
    risk_reward: Mapped[str | None] = mapped_column(Text)
    position_sizing: Mapped[str | None] = mapped_column(Text)
    confirmation_condition: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    invalidation: Mapped[str | None] = mapped_column(Text)
    trailing_stop: Mapped[str | None] = mapped_column(Text)

    # ── Scoring / market metadata ──
    price: Mapped[float | None] = mapped_column(Float)
    change_pct: Mapped[float | None] = mapped_column(Float)
    score: Mapped[float | None] = mapped_column(Float)
    strength: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)

    # ── Full serialized payload (the complete journal entry) ──
    full_signal: Mapped[dict | None] = mapped_column(JSON)


class PaperTradeModel(TimestampMixin, Base):
    """One simulated (paper) trade — opened from a buy signal, closed on exit."""

    __tablename__ = "paper_trades"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    signal_snapshot_id: Mapped[str | None] = mapped_column(String(50), index=True)

    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(120))
    market: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    source: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[float | None] = mapped_column(Float)
    score: Mapped[float | None] = mapped_column(Float)

    # ── Entry (from the buy signal) ──
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss_price: Mapped[float | None] = mapped_column(Float)
    target1_price: Mapped[float | None] = mapped_column(Float)
    target2_price: Mapped[float | None] = mapped_column(Float)
    quantity: Mapped[float] = mapped_column(Float, default=0)
    capital_allocated: Mapped[float] = mapped_column(Float, default=0)
    opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    entry_notes: Mapped[str | None] = mapped_column(Text)  # reason / confirmation of the signal

    # ── Exit ──
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    exit_price: Mapped[float | None] = mapped_column(Float)
    exit_reason: Mapped[str | None] = mapped_column(String(30))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    exit_notes: Mapped[str | None] = mapped_column(Text)

    # ── Accounting ──
    pnl: Mapped[float | None] = mapped_column(Float)
    pnl_pct: Mapped[float | None] = mapped_column(Float)
    holding_days: Mapped[int | None] = mapped_column(Integer)


class PaperEquityModel(TimestampMixin, Base):
    """Daily equity curve of the paper-trading account."""

    __tablename__ = "paper_equity_history"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    equity: Mapped[float] = mapped_column(Float, nullable=False)
    cash: Mapped[float] = mapped_column(Float, default=0)
    open_value: Mapped[float] = mapped_column(Float, default=0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0)
    open_positions: Mapped[int] = mapped_column(Integer, default=0)
    total_closed: Mapped[int] = mapped_column(Integer, default=0)
