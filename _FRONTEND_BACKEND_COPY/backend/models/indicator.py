from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class IndicatorModel(TimestampMixin, Base):
    __tablename__ = "indicators"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str | None] = mapped_column(String(50), index=True)
    indicator_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    params: Mapped[str | None] = mapped_column(Text)
    values: Mapped[str | None] = mapped_column(Text)
    timeframe: Mapped[str | None] = mapped_column(String(10), server_default="1d", index=True)
    date: Mapped[str | None] = mapped_column(String(20), index=True)
    data_source: Mapped[str | None] = mapped_column(String(20), server_default="system")
