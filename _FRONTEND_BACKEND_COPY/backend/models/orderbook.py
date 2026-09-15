from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class OrderbookModel(TimestampMixin, Base):
    __tablename__ = "orderbooks"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str | None] = mapped_column(String(50), index=True)
    bids: Mapped[str | None] = mapped_column(Text)
    asks: Mapped[str | None] = mapped_column(Text)
    time: Mapped[str | None] = mapped_column(String(20))
    date: Mapped[str | None] = mapped_column(String(20), index=True)
    data_source: Mapped[str | None] = mapped_column(String(20), server_default="tsetmc")
