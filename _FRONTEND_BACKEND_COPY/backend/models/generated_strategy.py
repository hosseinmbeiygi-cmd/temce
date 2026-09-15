"""Database model for storing generated strategy results."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class GeneratedStrategyModel(TimestampMixin, Base):
    """Stores results of strategy composition + backtesting."""

    __tablename__ = "generated_strategies"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Strategy config (JSON)
    entry_indicator: Mapped[str | None] = mapped_column(String(50), index=True)
    entry_params: Mapped[str | None] = mapped_column(Text)
    entry_condition: Mapped[str | None] = mapped_column(String(50))
    exit_indicator: Mapped[str | None] = mapped_column(String(50), index=True)
    exit_params: Mapped[str | None] = mapped_column(Text)
    exit_condition: Mapped[str | None] = mapped_column(String(50))
    filter1_indicator: Mapped[str | None] = mapped_column(String(50))
    filter1_params: Mapped[str | None] = mapped_column(Text)
    filter1_condition: Mapped[str | None] = mapped_column(String(50))
    filter2_indicator: Mapped[str | None] = mapped_column(String(50))
    filter2_params: Mapped[str | None] = mapped_column(Text)
    filter2_condition: Mapped[str | None] = mapped_column(String(50))
    stop_loss_pct: Mapped[float | None] = mapped_column(Float)
    take_profit_pct: Mapped[float | None] = mapped_column(Float)
    trailing_stop: Mapped[bool | None] = mapped_column(String(5))
    sizing_method: Mapped[str | None] = mapped_column(String(20))
    sizing_value: Mapped[float | None] = mapped_column(Float)

    # Metrics
    total_return_pct: Mapped[float | None] = mapped_column(Float)
    annualized_return_pct: Mapped[float | None] = mapped_column(Float)
    sharpe_ratio: Mapped[float | None] = mapped_column(Float, index=True)
    sortino_ratio: Mapped[float | None] = mapped_column(Float)
    calmar_ratio: Mapped[float | None] = mapped_column(Float)
    max_drawdown_pct: Mapped[float | None] = mapped_column(Float)
    win_rate: Mapped[float | None] = mapped_column(Float)
    profit_factor: Mapped[float | None] = mapped_column(Float)
    total_trades: Mapped[int | None] = mapped_column(Integer)
    winning_trades: Mapped[int | None] = mapped_column(Integer)
    losing_trades: Mapped[int | None] = mapped_column(Integer)

    # Score & meta
    score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    strategy_type: Mapped[str | None] = mapped_column(String(50))
    batch_id: Mapped[str | None] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20), server_default="active", index=True)


class GenerationBatchModel(TimestampMixin, Base):
    """Tracks each batch/phase of strategy generation."""

    __tablename__ = "generation_batches"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    symbols: Mapped[str | None] = mapped_column(Text)  # JSON array
    total_configs: Mapped[int | None] = mapped_column(Integer)
    pre_filtered: Mapped[int | None] = mapped_column(Integer)
    tested: Mapped[int | None] = mapped_column(Integer)
    passed_filter: Mapped[int | None] = mapped_column(Integer)
    saved_to_db: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(String(20), server_default="queued")
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
