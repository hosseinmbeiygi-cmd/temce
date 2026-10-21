from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class SymbolAlertModel(TimestampMixin, Base):
    __tablename__ = "symbol_alerts"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), index=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    market: Mapped[str | None] = mapped_column(String(20))
    base_price: Mapped[float] = mapped_column(Float, server_default="0")
    trigger_rules: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.text("true"), index=True)


class SymbolAssessmentSnapshotModel(Base):
    __tablename__ = "symbol_assessment_snapshots"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), index=True)
    symbol: Mapped[str] = mapped_column(String(50), index=True)
    market: Mapped[str | None] = mapped_column(String(20))
    market_metrics: Mapped[str | None] = mapped_column(Text)
    ml_prediction: Mapped[str | None] = mapped_column(Text)
    backtest_summary: Mapped[str | None] = mapped_column(Text)
    codal_signals: Mapped[str | None] = mapped_column(Text)
    decision_summary: Mapped[str | None] = mapped_column(Text)
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime)
