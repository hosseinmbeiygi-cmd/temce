"""SQLAlchemy model for manual USD/USDT positions.

Lives in ``models/`` so it registers into the shared ``Base.metadata`` via
``models/__init__.py``. Owned by ``apps.currency_service`` — that service
imports this model through the central ``models`` package.

Single table, no FK (user_id is an opaque string; actual identity lives in
apps/api auth tables).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class CurrencyManualPositionModel(Base):
    """One manually-tracked cash USD or USDT position."""

    __tablename__ = "currency_manual_positions"

    id: Mapped[int] = mapped_column(Numeric(18, 0), primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(16), nullable=False)  # CASH_USD | USDT
    entry_price: Mapped[float] = mapped_column(Numeric(18, 0), nullable=False)
    volume: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_currency_positions_user_asset", "user_id", "asset_type"),)
