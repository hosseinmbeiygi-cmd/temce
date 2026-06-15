from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class TradeModel(TimestampMixin, Base):
    __tablename__ = "trades"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str | None] = mapped_column(String(50))
    price: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[int | None] = mapped_column(Integer)
    value: Mapped[float | None] = mapped_column(Float)
    side: Mapped[str | None] = mapped_column(String(10))
    time: Mapped[str | None] = mapped_column(String(20))
    date: Mapped[str | None] = mapped_column(String(20), index=True)
    data_source: Mapped[str | None] = mapped_column(String(20), server_default="tsetmc")
