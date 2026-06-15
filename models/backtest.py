from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class BacktestRunModel(TimestampMixin, Base):
    __tablename__ = "backtest_runs"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    strategy_type: Mapped[str | None] = mapped_column(String(100))
    symbols: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(20), server_default="queued")
    start_date: Mapped[str | None] = mapped_column(String(20))
    end_date: Mapped[str | None] = mapped_column(String(20))
    initial_capital: Mapped[float | None] = mapped_column(Float)
    current_value: Mapped[float | None] = mapped_column(Float)
    total_return_pct: Mapped[float | None] = mapped_column(Float)
    commission_pct: Mapped[float | None] = mapped_column(Float, server_default="0.0035")
    slippage_bps: Mapped[float | None] = mapped_column(Float, server_default="10")
    strategy_params: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[str | None] = mapped_column(Text)
    progress_pct: Mapped[float | None] = mapped_column(Float, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by: Mapped[str | None] = mapped_column(String(100), server_default="system")


class BacktestTradeModel(TimestampMixin, Base):
    __tablename__ = "backtest_trades"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(50), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(50))
    direction: Mapped[str | None] = mapped_column(String(10))
    entry_date: Mapped[str | None] = mapped_column(String(20))
    exit_date: Mapped[str | None] = mapped_column(String(20))
    entry_price: Mapped[float | None] = mapped_column(Float)
    exit_price: Mapped[float | None] = mapped_column(Float)
    quantity: Mapped[int | None] = mapped_column(Integer)
    gross_profit: Mapped[float | None] = mapped_column(Float)
    net_profit: Mapped[float | None] = mapped_column(Float)
    return_pct: Mapped[float | None] = mapped_column(Float)
    commission: Mapped[float | None] = mapped_column(Float)
    exit_reason: Mapped[str | None] = mapped_column(String(50))
