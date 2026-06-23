from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class RecommendationModel(TimestampMixin, Base):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    instrument_id: Mapped[str | None] = mapped_column(String(50), index=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    confidence: Mapped[float | None] = mapped_column(Float, server_default="0")
    target_price: Mapped[float | None] = mapped_column(Float)
    stop_loss: Mapped[float | None] = mapped_column(Float)
    rationale: Mapped[str | None] = mapped_column(Text)
    strategy: Mapped[str | None] = mapped_column(String(50))
    risk_level: Mapped[str | None] = mapped_column(String(20))
    horizon: Mapped[str | None] = mapped_column(String(20))
    data_source: Mapped[str | None] = mapped_column(String(20), server_default="system")
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now(), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
