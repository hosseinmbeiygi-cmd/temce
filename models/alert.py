from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class AlertModel(TimestampMixin, Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    instrument_id: Mapped[str | None] = mapped_column(String(50), index=True)
    symbol: Mapped[str | None] = mapped_column(String(50))
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    condition: Mapped[str | None] = mapped_column(Text)
    channels: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool | None] = mapped_column(Boolean, server_default=sa.text("true"), index=True)
    triggered_count: Mapped[int | None] = mapped_column(Integer, server_default="0")
    last_triggered: Mapped[datetime | None] = mapped_column(DateTime)
    description: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    # --- signal/market link (add-to-alerts from any section) ---
    signal_id: Mapped[str | None] = mapped_column(String(50), index=True)
    market: Mapped[str | None] = mapped_column(String(20), index=True)
    timeframe: Mapped[str | None] = mapped_column(String(10))


class AlertHistoryModel(Base):
    __tablename__ = "alert_history"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
    trigger_value: Mapped[float | None] = mapped_column(Float)
    message: Mapped[str | None] = mapped_column(Text)
    delivered: Mapped[bool | None] = mapped_column(Boolean, server_default=sa.text("false"))
