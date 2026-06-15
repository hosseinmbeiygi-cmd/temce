from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "instruments",
        sa.Column("instrument_type", sa.String(30), nullable=True, server_default="stock"),
    )

    op.create_table(
        "instrument_external_ids",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("instrument_id", sa.String(50), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("source", "external_id", name="uq_source_external_id"),
    )
    op.create_table(
        "symbol_aliases",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("instrument_id", sa.String(50), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("source", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("instrument_id", "symbol", name="uq_instrument_symbol"),
    )
    op.create_table(
        "trade_ticks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("instrument_id", sa.String(50), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("trade_date", sa.BigInteger(), nullable=True, comment="YYYYMMDD"),
        sa.Column("price", sa.Numeric(20, 4), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("value", sa.Numeric(24, 4), nullable=True),
        sa.Column("trade_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_trade_ticks_instrument_date", "trade_ticks", ["instrument_id", "trade_date"])
    op.create_table(
        "market_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("instrument_id", sa.String(50), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("last_price", sa.Numeric(20, 4), nullable=True),
        sa.Column("close_price", sa.Numeric(20, 4), nullable=True),
        sa.Column("first_price", sa.Numeric(20, 4), nullable=True),
        sa.Column("high_price", sa.Numeric(20, 4), nullable=True),
        sa.Column("low_price", sa.Numeric(20, 4), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("value", sa.Numeric(24, 4), nullable=True),
        sa.Column("trade_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("yesterday_close", sa.Numeric(20, 4), nullable=True),
        sa.Column("eps", sa.Numeric(20, 4), nullable=True),
        sa.Column("base_volume", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_market_snapshots_instrument", "market_snapshots", ["instrument_id"])
    op.create_table(
        "orderbook_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("instrument_id", sa.String(50), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("side", sa.String(4), nullable=False, comment="bid/ask"),
        sa.Column("price", sa.Numeric(20, 4), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("order_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_orderbook_events_instrument_side", "orderbook_events", ["instrument_id", "side"])
    op.create_table(
        "daily_ohlcv",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("instrument_id", sa.String(50), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("trade_date", sa.BigInteger(), nullable=False, comment="YYYYMMDD"),
        sa.Column("open", sa.Numeric(20, 4), nullable=True),
        sa.Column("high", sa.Numeric(20, 4), nullable=True),
        sa.Column("low", sa.Numeric(20, 4), nullable=True),
        sa.Column("close", sa.Numeric(20, 4), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("value", sa.Numeric(24, 4), nullable=True),
        sa.Column("trade_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("instrument_id", "trade_date", name="uq_daily_ohlcv_instrument_date"),
    )


def downgrade() -> None:
    op.drop_table("daily_ohlcv")
    op.drop_table("orderbook_events")
    op.drop_table("market_snapshots")
    op.drop_table("trade_ticks")
    op.drop_table("symbol_aliases")
    op.drop_table("instrument_external_ids")
    op.drop_column("instruments", "instrument_type")
