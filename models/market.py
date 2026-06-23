from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class MarketModel(TimestampMixin, Base):
    __tablename__ = "markets"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    market_type: Mapped[str | None] = mapped_column(String(20), index=True)
    exchange_code: Mapped[str | None] = mapped_column(String(20), index=True)
    country: Mapped[str | None] = mapped_column(String(50), server_default="IR")
    timezone: Mapped[str | None] = mapped_column(String(50), server_default="Asia/Tehran")
    open_time: Mapped[str | None] = mapped_column(String(10), server_default="09:00")
    close_time: Mapped[str | None] = mapped_column(String(10), server_default="12:30")
    status: Mapped[str | None] = mapped_column(String(20), server_default="active")
    description: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
