"""
Cryptocurrency price ORM model.

Stores prices from the ``/Market/Cryptocurrency.php`` endpoint.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from brsapi.models.base import BrsApiBase, InstrumentRefMixin


class CryptoPriceModel(InstrumentRefMixin, BrsApiBase):
    """
    Cryptocurrency prices (Bitcoin, Ethereum, 3000+ coins).

    One row per crypto per fetch with USD and IRR/TOMAN prices.
    """

    __tablename__ = "brsapi_crypto_prices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    price_usd: Mapped[float | None] = mapped_column(Float)
    price_toman: Mapped[float | None] = mapped_column(Float)
    price_irr: Mapped[float | None] = mapped_column(Float)
    change_percent: Mapped[float | None] = mapped_column(Float)
    market_cap: Mapped[float | None] = mapped_column(Float)
    volume_24h: Mapped[float | None] = mapped_column(Float)
    icon_url: Mapped[str | None] = mapped_column(String(500))
    rank: Mapped[int | None] = mapped_column(Integer, default=0, server_default="0")
    date: Mapped[str | None] = mapped_column(String(20))
    time: Mapped[str | None] = mapped_column(String(20))
    time_unix: Mapped[int | None] = mapped_column(BigInteger)
    fetched_at: Mapped[str | None] = mapped_column(String(30))
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_crypto_symbol_fetched", "symbol", "fetched_at"),
        Index("idx_crypto_rank", "rank"),
    )
