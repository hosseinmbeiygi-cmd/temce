from sqlalchemy import BigInteger, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class QuoteModel(TimestampMixin, Base):
    __tablename__ = "quotes"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str | None] = mapped_column(String(50), index=True)
    price_close: Mapped[float | None] = mapped_column(Float)
    price_open: Mapped[float | None] = mapped_column(Float)
    price_high: Mapped[float | None] = mapped_column(Float)
    price_low: Mapped[float | None] = mapped_column(Float)
    price_last: Mapped[float | None] = mapped_column(Float)
    price_change: Mapped[float | None] = mapped_column(Float)
    price_change_pct: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[int | None] = mapped_column(BigInteger)
    value: Mapped[float | None] = mapped_column(Float)
    trade_count: Mapped[int | None] = mapped_column(BigInteger)
    price_yesterday: Mapped[float | None] = mapped_column(Float)
    price_first: Mapped[float | None] = mapped_column(Float)
    price_max: Mapped[float | None] = mapped_column(Float)
    price_min: Mapped[float | None] = mapped_column(Float)
    ask_price: Mapped[float | None] = mapped_column(Float)
    ask_volume: Mapped[int | None] = mapped_column(BigInteger)
    bid_price: Mapped[float | None] = mapped_column(Float)
    bid_volume: Mapped[int | None] = mapped_column(BigInteger)
    time: Mapped[str | None] = mapped_column(String(20))
    date: Mapped[str | None] = mapped_column(String(20), index=True)
    timeframe: Mapped[str | None] = mapped_column(String(10), server_default="1d")
    data_source: Mapped[str | None] = mapped_column(String(20), server_default="tsetmc")
