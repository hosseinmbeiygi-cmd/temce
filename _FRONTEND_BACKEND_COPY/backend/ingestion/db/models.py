from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import MetaData, func

metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    },
)

instrument_external_ids = sa.Table(
    "instrument_external_ids",
    metadata,
    sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
    sa.Column("instrument_id", sa.String(50), sa.ForeignKey("instruments.id"), nullable=False),
    sa.Column("source", sa.String(30), nullable=False),
    sa.Column("external_id", sa.String(100), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now()),
    sa.UniqueConstraint("source", "external_id", name="uq_source_external_id"),
)

symbol_aliases = sa.Table(
    "symbol_aliases",
    metadata,
    sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
    sa.Column("instrument_id", sa.String(50), sa.ForeignKey("instruments.id"), nullable=False),
    sa.Column("symbol", sa.String(50), nullable=False),
    sa.Column("source", sa.String(30), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now()),
    sa.UniqueConstraint("instrument_id", "symbol", name="uq_instrument_symbol"),
)

trade_ticks = sa.Table(
    "trade_ticks",
    metadata,
    sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
    sa.Column("instrument_id", sa.String(50), sa.ForeignKey("instruments.id"), nullable=False),
    sa.Column("trade_date", sa.BigInteger, nullable=True, comment="YYYYMMDD"),
    sa.Column("price", sa.Numeric(20, 4), nullable=True),
    sa.Column("volume", sa.BigInteger, nullable=False, server_default="0"),
    sa.Column("value", sa.Numeric(24, 4), nullable=True),
    sa.Column("trade_count", sa.Integer, nullable=False, server_default="0"),
    sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=func.now()),
    sa.Index("ix_trade_ticks_instrument_date", "instrument_id", "trade_date"),
)

market_snapshots = sa.Table(
    "market_snapshots",
    metadata,
    sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
    sa.Column("instrument_id", sa.String(50), sa.ForeignKey("instruments.id"), nullable=False),
    sa.Column("last_price", sa.Numeric(20, 4), nullable=True),
    sa.Column("close_price", sa.Numeric(20, 4), nullable=True),
    sa.Column("first_price", sa.Numeric(20, 4), nullable=True),
    sa.Column("high_price", sa.Numeric(20, 4), nullable=True),
    sa.Column("low_price", sa.Numeric(20, 4), nullable=True),
    sa.Column("volume", sa.BigInteger, nullable=False, server_default="0"),
    sa.Column("value", sa.Numeric(24, 4), nullable=True),
    sa.Column("trade_count", sa.Integer, nullable=False, server_default="0"),
    sa.Column("yesterday_close", sa.Numeric(20, 4), nullable=True),
    sa.Column("eps", sa.Numeric(20, 4), nullable=True),
    sa.Column("base_volume", sa.BigInteger, nullable=False, server_default="0"),
    sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=func.now()),
    sa.Index("ix_market_snapshots_instrument", "instrument_id"),
)

orderbook_events = sa.Table(
    "orderbook_events",
    metadata,
    sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
    sa.Column("instrument_id", sa.String(50), sa.ForeignKey("instruments.id"), nullable=False),
    sa.Column("side", sa.String(4), nullable=False, comment="bid/ask"),
    sa.Column("price", sa.Numeric(20, 4), nullable=True),
    sa.Column("volume", sa.BigInteger, nullable=False, server_default="0"),
    sa.Column("order_count", sa.Integer, nullable=False, server_default="0"),
    sa.Column("rank", sa.Integer, nullable=False, server_default="0"),
    sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=func.now()),
    sa.Index("ix_orderbook_events_instrument_side", "instrument_id", "side"),
)

daily_ohlcv = sa.Table(
    "daily_ohlcv",
    metadata,
    sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
    sa.Column("instrument_id", sa.String(50), sa.ForeignKey("instruments.id"), nullable=False),
    sa.Column("trade_date", sa.BigInteger, nullable=False, comment="YYYYMMDD"),
    sa.Column("open", sa.Numeric(20, 4), nullable=True),
    sa.Column("high", sa.Numeric(20, 4), nullable=True),
    sa.Column("low", sa.Numeric(20, 4), nullable=True),
    sa.Column("close", sa.Numeric(20, 4), nullable=True),
    sa.Column("volume", sa.BigInteger, nullable=False, server_default="0"),
    sa.Column("value", sa.Numeric(24, 4), nullable=True),
    sa.Column("trade_count", sa.Integer, nullable=False, server_default="0"),
    sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=func.now()),
    sa.UniqueConstraint("instrument_id", "trade_date", name="uq_daily_ohlcv_instrument_date"),
)
