from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class InstrumentModel(TimestampMixin, Base):
    __tablename__ = "instruments"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    isin: Mapped[str | None] = mapped_column(String(50), unique=True)
    market_type: Mapped[str | None] = mapped_column(String(20))
    asset_class: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str | None] = mapped_column(String(20), server_default="active")
    sector_code: Mapped[str | None] = mapped_column(String(20))
    group_code: Mapped[str | None] = mapped_column(String(20))
    sub_group_code: Mapped[str | None] = mapped_column(String(20))
    tick_size: Mapped[float | None] = mapped_column(Float, server_default="1.0")
    lot_size: Mapped[int | None] = mapped_column(Integer, server_default="1")
    par_value: Mapped[int | None] = mapped_column(Integer, server_default="1000")
    eps: Mapped[float | None] = mapped_column(Float, server_default="0")
    shares_count: Mapped[int | None] = mapped_column(BigInteger, server_default="0")
    base_volume: Mapped[int | None] = mapped_column(BigInteger, server_default="0")
    market_id: Mapped[str | None] = mapped_column(String(50))
    exchange_code: Mapped[str | None] = mapped_column(String(20))
    board_code: Mapped[str | None] = mapped_column(String(20))
    data_source: Mapped[str | None] = mapped_column(String(20), server_default="tsetmc")
    tags: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
