from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class SignalModel(TimestampMixin, Base):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    instrument_id: Mapped[str | None] = mapped_column(String(50), index=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    signal_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    strength: Mapped[float | None] = mapped_column(Float, server_default="0")
    direction: Mapped[str | None] = mapped_column(String(20), index=True)
    source: Mapped[str | None] = mapped_column(String(100))
    indicators: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    timeframe: Mapped[str | None] = mapped_column(String(10), server_default="1d")
    data_source: Mapped[str | None] = mapped_column(String(20), server_default="system")
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now(), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
