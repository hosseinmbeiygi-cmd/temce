"""Gold options derivatives persistence (STEP 5-FIX-2).

Table ``gold_option_iv_history`` — one daily implied-volatility observation
per contract, written by ``GoldOptionIvSnapshotJob`` and read back by
``ImeOptionsChainProvider.load_iv_history`` to feed ``iv_rank`` /
``iv_percentile``.  Idempotent per ``(symbol, as_of, strike)``.
"""

from __future__ import annotations

from datetime import date

import sqlalchemy as sa
from sqlalchemy import BigInteger, Date, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin


class GoldOptionIvHistoryModel(TimestampMixin, Base):
    """One daily IV observation for one option contract strike."""

    __tablename__ = "gold_option_iv_history"

    __table_args__ = (
        sa.UniqueConstraint(
            "symbol",
            "as_of",
            "strike",
            name="uq_gold_option_iv_history_symbol_as_of_strike",
        ),
    )

    id: Mapped[int] = mapped_column(
        # ``BigInteger`` autoincrement is a Postgres feature; SQLite (unit
        # tests) needs a plain INTEGER primary key for rowid aliasing.
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    # Option contract code (the chain's contract_key).
    symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expiry: Mapped[str | None] = mapped_column(String(32))
    strike: Mapped[float] = mapped_column(Float, nullable=False)
    iv: Mapped[float] = mapped_column(Float, nullable=False)
    forward: Mapped[float | None] = mapped_column(Float)
    as_of: Mapped[date] = mapped_column(Date, nullable=False, index=True)
