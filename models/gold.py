"""Gold module models — Iranian gold market persistence layer.

Three tables power the gold module:

1. ``gold_futures_positions`` — open/closed leveraged positions on IME coin
   futures. Tracks entry, liquidation price, current health, leverage, and
   realized/unrealized P&L.

2. ``gold_kill_switch_events`` — append-only log of kill-switch triggers
   (volatility circuit breakers, margin shocks, market freezes).

3. ``gold_portfolio_holdings`` — manual trade journal of physical gold,
   ETFs, and non-leveraged positions for the dollar-adjusted return view.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin

# ────────────────────────────────────────────────────────────────────
# 1. Futures Positions (IME coin futures)
# ────────────────────────────────────────────────────────────────────


class GoldFuturesPositionModel(TimestampMixin, Base):
    """یک پوزیشن آتی سکه (باز یا بسته)."""

    __tablename__ = "gold_futures_positions"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    contract_symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # e.g. "سکه_آتی_IME_1404_اسفند"
    position_type: Mapped[str] = mapped_column(String(10), nullable=False)  # LONG/SHORT
    leverage: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    # ── Entry ──
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    initial_margin: Mapped[float] = mapped_column(Float, nullable=False)
    maintenance_margin: Mapped[float] = mapped_column(Float, nullable=False)
    liquidation_price: Mapped[float] = mapped_column(Float, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    entry_notes: Mapped[str | None] = mapped_column(Text)

    # ── Risk controls ──
    stop_loss: Mapped[float | None] = mapped_column(Float)
    target_1: Mapped[float | None] = mapped_column(Float)
    target_2: Mapped[float | None] = mapped_column(Float)

    # ── Current snapshot (updated by price feed) ──
    current_price: Mapped[float | None] = mapped_column(Float)
    last_price_update: Mapped[datetime | None] = mapped_column(DateTime)
    unrealized_pnl: Mapped[float | None] = mapped_column(Float)
    unrealized_pnl_pct: Mapped[float | None] = mapped_column(Float)
    health_ratio: Mapped[float | None] = mapped_column(Float)
    distance_to_liquidation_pct: Mapped[float | None] = mapped_column(Float)

    # ── Exit ──
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="OPEN", index=True
    )  # OPEN/CLOSED/LIQUIDATED
    exit_price: Mapped[float | None] = mapped_column(Float)
    exit_reason: Mapped[str | None] = mapped_column(String(30))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    realized_pnl: Mapped[float | None] = mapped_column(Float)
    realized_pnl_pct: Mapped[float | None] = mapped_column(Float)


# ────────────────────────────────────────────────────────────────────
# 2. Kill-Switch event log
# ────────────────────────────────────────────────────────────────────


class GoldKillSwitchEventModel(TimestampMixin, Base):
    """رویداد ثبت‌شده هنگام فعال شدن Kill-Switch."""

    __tablename__ = "gold_kill_switch_events"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # WARNING/ACTIVE
    rule: Mapped[str] = mapped_column(String(50), nullable=False)
    # volatility_circuit_breaker / futures_margin_shock / systemic_freeze
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolution: Mapped[str | None] = mapped_column(Text)


# ────────────────────────────────────────────────────────────────────
# 3. Portfolio Holdings (manual trade journal)
# ────────────────────────────────────────────────────────────────────


class GoldPortfolioHoldingModel(TimestampMixin, Base):
    """سابقه معاملات دستی طلا (فیزیکی، ETF، غیر اهرمی)."""

    __tablename__ = "gold_portfolio_holdings"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    asset_symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    asset_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # PHYSICAL_GOLD / ETF / COIN_PHYSICAL / OUNCE

    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    entry_price_irr: Mapped[float] = mapped_column(Float, nullable=False)
    entry_usd_rate: Mapped[float] = mapped_column(Float, nullable=False)
    entry_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    fees_pct: Mapped[float] = mapped_column(Float, default=0.0)

    # Optional exit (برای محاسبه P&L بسته)
    exit_price_irr: Mapped[float | None] = mapped_column(Float)
    exit_usd_rate: Mapped[float | None] = mapped_column(Float)
    exit_date: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN", index=True)  # OPEN/CLOSED

    realized_pnl_irr: Mapped[float | None] = mapped_column(Float)
    realized_dollar_roi_pct: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
