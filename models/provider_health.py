from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class ProviderHealthModel(TimestampMixin, Base):
    __tablename__ = "provider_health"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    status: Mapped[str | None] = mapped_column(String(20), server_default="unknown")
    latency_ms: Mapped[float | None] = mapped_column(Float, server_default="0")
    last_success: Mapped[datetime | None] = mapped_column(DateTime)
    last_failure: Mapped[datetime | None] = mapped_column(DateTime)
    consecutive_failures: Mapped[int | None] = mapped_column(Integer, server_default="0")
    uptime_pct: Mapped[float | None] = mapped_column(Float, server_default="100")
    error_message: Mapped[str | None] = mapped_column(Text)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)


class ProviderHealthHistoryModel(Base):
    __tablename__ = "provider_health_history"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str | None] = mapped_column(String(20))
    latency_ms: Mapped[float | None] = mapped_column(Float)
    error_message: Mapped[str | None] = mapped_column(Text)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
