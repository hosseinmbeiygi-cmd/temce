"""Create TimescaleDB hypertables for trade_ticks and daily_ohlcv.

Revision ID: 0021
Revises: 0020
"""
from __future__ import annotations

from typing import ClassVar

from alembic import op

revision: str = "0021"
down_revision: ClassVar[str | None] = "0020"
branch_labels: ClassVar[str | None] = None
depends_on: ClassVar[str | None] = None


def upgrade() -> None:
    """Convert trade_ticks and daily_ohlcv to TimescaleDB hypertables.

    trade_ticks  → partitioned by fetched_at (TIMESTAMPTZ, 1-day chunks)
    daily_ohlcv  → partitioned by trade_date (BIGINT YYYYMMDD, 1 unit = 1 day)
    """
    # Step 1: Enable the TimescaleDB extension
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")

    # Step 2: Convert trade_ticks – hourly trade data
    op.execute(
        "SELECT create_hypertable("
        "    'trade_ticks',"
        "    'fetched_at',"
        "    chunk_time_interval => INTERVAL '1 day',"
        "    if_not_exists => TRUE,"
        "    migrate_data => TRUE"
        ")"
    )

    # Enable native compression after 7 days
    op.execute(
        "ALTER TABLE trade_ticks SET ("
        "    timescaledb.compress,"
        "    timescaledb.compress_segmentby = 'instrument_id',"
        "    timescaledb.compress_orderby = 'fetched_at DESC'"
        ")"
    )
    op.execute(
        "SELECT add_compression_policy('trade_ticks', INTERVAL '7 days', if_not_exists => TRUE)"
    )

    # Step 3: Convert daily_ohlcv – daily candle data
    # trade_date is BIGINT (YYYYMMDD format, e.g. 20240115).
    # chunk_time_interval => 1 means one chunk per calendar day.
    op.execute(
        "SELECT create_hypertable("
        "    'daily_ohlcv',"
        "    'trade_date',"
        "    chunk_time_interval => 1,"
        "    if_not_exists => TRUE,"
        "    migrate_data => TRUE"
        ")"
    )

    # Enable native compression after 30 days
    op.execute(
        "ALTER TABLE daily_ohlcv SET ("
        "    timescaledb.compress,"
        "    timescaledb.compress_segmentby = 'instrument_id',"
        "    timescaledb.compress_orderby = 'trade_date DESC'"
        ")"
    )
    op.execute(
        "SELECT add_compression_policy('daily_ohlcv', INTERVAL '30 days', if_not_exists => TRUE)"
    )


def downgrade() -> None:
    """Downgrade is not supported for hypertable conversion.

    There is no built-in way to convert a hypertable back to a plain table.
    To manually revert:
        1. CREATE TABLE trade_ticks_plain (LIKE trade_ticks INCLUDING ALL);
        2. INSERT INTO trade_ticks_plain SELECT * FROM trade_ticks;
        3. DROP TABLE trade_ticks CASCADE;
        4. ALTER TABLE trade_ticks_plain RENAME TO trade_ticks;
       (repeat for daily_ohlcv)
    """
    op.execute("SELECT remove_compression_policy('trade_ticks', if_not_exists => TRUE)")
    op.execute("SELECT remove_compression_policy('daily_ohlcv', if_not_exists => TRUE)")
    raise NotImplementedError(
        "Cannot automatically revert hypertable conversion. "
        "See docstring in downgrade() for manual steps."
    )
