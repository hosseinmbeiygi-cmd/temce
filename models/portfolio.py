from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class PortfolioModel(TimestampMixin, Base):
    __tablename__ = "portfolios"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    initial_capital: Mapped[float | None] = mapped_column(Float, server_default="0")
    current_value: Mapped[float | None] = mapped_column(Float, server_default="0")
    currency: Mapped[str | None] = mapped_column(String(10), server_default="IRR")
    owner: Mapped[str | None] = mapped_column(String(100), server_default="system")
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class PortfolioPositionModel(TimestampMixin, Base):
    __tablename__ = "portfolio_positions"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(String(50), nullable=False)
    instrument_id: Mapped[str | None] = mapped_column(String(50))
    symbol: Mapped[str | None] = mapped_column(String(50))
    quantity: Mapped[int | None] = mapped_column(Integer)
    avg_cost: Mapped[float | None] = mapped_column(Float)
    current_price: Mapped[float | None] = mapped_column(Float)
    market_value: Mapped[float | None] = mapped_column(Float)
    unrealized_pnl: Mapped[float | None] = mapped_column(Float)
    weight_pct: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
