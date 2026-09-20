"""Corporate-action event ledger + materialized cumulative adjust factors.

Audit gap §2 (2026-09-21): indicators were computed on raw TSETMC prices.
These models back the new tables of migration 0061; the factor semantics
live in ``services/corporate_action_service.py`` so both backfill scripts
and the runtime recomputation share one implementation.
"""

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class CorporateActionModel(Base):
    __tablename__ = "corporate_actions"

    symbol_id: Mapped[int] = mapped_column(
        ForeignKey("symbols.id", ondelete="CASCADE"), primary_key=True
    )
    ex_date: Mapped[object] = mapped_column(Date, primary_key=True)
    action_type: Mapped[str] = mapped_column(String(20), primary_key=True)
    ratio: Mapped[float] = mapped_column(Numeric(12, 6), default=0)
    dps: Mapped[float] = mapped_column(Numeric(20, 2), default=0)
    source: Mapped[str] = mapped_column(String(20), default="manual")
    codal_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(
        Date, nullable=False, server_default="now()"
    )


class DailyAdjustFactorModel(TimestampMixin, Base):
    __tablename__ = "daily_adjust_factors"

    symbol_id: Mapped[int] = mapped_column(
        ForeignKey("symbols.id", ondelete="CASCADE"), primary_key=True
    )
    trade_date: Mapped[object] = mapped_column(Date, primary_key=True)
    adj_factor: Mapped[float] = mapped_column(Numeric(18, 10), default=1)
