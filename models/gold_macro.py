"""Gold macro / sentiment persistence layer.

Tables:

1. ``gold_macro_indicators`` — FRED / external macro series (10Y TIPS real yield,
   broad dollar index) with provenance and ``fetched_at`` per row.
2. ``gold_cot_positions`` — CFTC Commitment of Traders gold futures positions
   (managed-money net, commercial net, weekly change, percentile).
3. ``gold_economic_calendar_events`` — CPI / NFP / FOMC high-volatility events
   with an ``is_high_volatility`` flag and ``fetched_at``.
4. ``gold_iran_manual_events`` — Iran-specific manual-entry calendar events
   (no external feed; entered by operators).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class GoldMacroIndicatorModel(TimestampMixin, Base):
    """One row per macro-indicator observation (FRED TIPS / DXY / …)."""

    __tablename__ = "gold_macro_indicators"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    indicator: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # e.g. FRED_DFII10 / FRED_DTWEXBGS
    country: Mapped[str | None] = mapped_column(
        String(50), server_default="global", index=True
    )
    value: Mapped[float | None] = mapped_column(Float)
    previous_value: Mapped[float | None] = mapped_column(Float)
    change_pct: Mapped[float | None] = mapped_column(Float)
    as_of: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False)  # FRED / CFTC
    provenance: Mapped[str | None] = mapped_column(
        Text
    )  # series id + query URL / request params
    unit: Mapped[str | None] = mapped_column(String(50))
    frequency: Mapped[str | None] = mapped_column(String(20))


class GoldCotPositionModel(TimestampMixin, Base):
    """One row per weekly CFTC COT gold futures report."""

    __tablename__ = "gold_cot_positions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    cftc_contract_market_code: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # e.g. 088691
    market_name: Mapped[str | None] = mapped_column(String(64))
    managed_money_long: Mapped[int | None] = mapped_column(BigInteger)
    managed_money_short: Mapped[int | None] = mapped_column(BigInteger)
    managed_money_net: Mapped[int | None] = mapped_column(BigInteger)
    managed_money_net_change: Mapped[int | None] = mapped_column(BigInteger)
    commercial_long: Mapped[int | None] = mapped_column(BigInteger)
    commercial_short: Mapped[int | None] = mapped_column(BigInteger)
    commercial_net: Mapped[int | None] = mapped_column(BigInteger)
    open_interest: Mapped[int | None] = mapped_column(BigInteger)
    managed_money_net_percentile: Mapped[float | None] = mapped_column(Float)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    source: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="CFTC"
    )
    provenance: Mapped[str | None] = mapped_column(Text)


class GoldEconomicCalendarEventModel(TimestampMixin, Base):
    """CPI / NFP / FOMC high-volatility calendar events (DB-backed)."""

    __tablename__ = "gold_economic_calendar_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    event_time: Mapped[str | None] = mapped_column(String(16))
    title: Mapped[str | None] = mapped_column(String(256))
    country: Mapped[str | None] = mapped_column(String(32), index=True)
    category: Mapped[str | None] = mapped_column(String(64), index=True)
    importance: Mapped[int | None] = mapped_column(Integer, server_default="2")
    is_high_volatility: Mapped[bool] = mapped_column(
        Boolean, server_default=sa.text("false")
    )
    source: Mapped[str | None] = mapped_column(String(64))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


class GoldIranManualEventModel(TimestampMixin, Base):
    """Iran-specific manual-entry calendar events (operators only)."""

    __tablename__ = "gold_iran_manual_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    event_time: Mapped[str | None] = mapped_column(String(16))
    title: Mapped[str | None] = mapped_column(String(256))
    category: Mapped[str | None] = mapped_column(String(64))
    importance: Mapped[int | None] = mapped_column(Integer, server_default="2")
    note: Mapped[str | None] = mapped_column(Text)
    is_high_volatility: Mapped[bool] = mapped_column(
        Boolean, server_default=sa.text("false")
    )


__all__ = [
    "GoldCotPositionModel",
    "GoldEconomicCalendarEventModel",
    "GoldIranManualEventModel",
    "GoldMacroIndicatorModel",
]
