from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
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
    # --- arch layers 4/6/12: standard schema fields ---
    market: Mapped[str | None] = mapped_column(String(20), default="stock", index=True)
    entry: Mapped[float | None] = mapped_column(Float, server_default="0")
    stop_loss: Mapped[float | None] = mapped_column(Float, server_default="0")
    take_profit: Mapped[float | None] = mapped_column(Float, server_default="0")
    confidence: Mapped[float | None] = mapped_column(Float, server_default="0")
    top_reasons: Mapped[str | None] = mapped_column(Text)  # JSON list
    backtest_stats: Mapped[str | None] = mapped_column(Text)  # JSON {win_rate,avg_return,sample_size,low_sample}
    eval_due_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    schema_version: Mapped[int | None] = mapped_column(Integer, server_default="1")
    model_version: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str | None] = mapped_column(String(20), server_default="pending", index=True)
    actual_outcome_price: Mapped[float | None] = mapped_column(Float)
    actual_return_pct: Mapped[float | None] = mapped_column(Float)
    was_correct: Mapped[bool | None] = mapped_column(Boolean)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime)
