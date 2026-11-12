"""Create missing ingestion core tables — audit DB-03

Revision ID: 0123
Revises: 0122
Create Date: 2026-11-13

``ingestion/db/models.py`` defines five core tables that StorageLayer and the
market-watch parsers INSERT into, but no earlier migration created them.
Migration 0103 already assumed they existed (and silently skipped them if not).

Tables added (all guarded with IF NOT EXISTS so a DB that had them created
out-of-band is not broken):
  - trade_ticks          — per-tick trade events
  - market_snapshots     — real-time snapshot rows
  - orderbook_events     — bid/ask order-book levels
  - daily_ohlcv          — EOD OHLCV bars
  - instrument_external_ids — source → instrument mapping
  - symbol_aliases       — symbol name aliases per instrument
  - armor_raw_ingest     — raw JSON snapshots from LayeredStoragePipeline
                           (previously created inline by layered_pipeline.py;
                           now brought under migration control)

Downgrade drops all seven tables.
"""
from __future__ import annotations

from alembic import op

revision = "0123"
down_revision = "0122"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS trade_ticks (
            id              BIGSERIAL PRIMARY KEY,
            instrument_id   VARCHAR(50) NOT NULL REFERENCES instruments(id),
            trade_date      BIGINT,
            price           NUMERIC(20,4),
            volume          BIGINT NOT NULL DEFAULT 0,
            value           NUMERIC(24,4),
            trade_count     INTEGER NOT NULL DEFAULT 0,
            fetched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            source_timestamp TIMESTAMPTZ
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_trade_ticks_instrument_date "
        "ON trade_ticks (instrument_id, trade_date)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_trade_ticks_src_ts "
        "ON trade_ticks (source_timestamp)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS market_snapshots (
            id              BIGSERIAL PRIMARY KEY,
            instrument_id   VARCHAR(50) NOT NULL REFERENCES instruments(id),
            last_price      NUMERIC(20,4),
            close_price     NUMERIC(20,4),
            first_price     NUMERIC(20,4),
            high_price      NUMERIC(20,4),
            low_price       NUMERIC(20,4),
            volume          BIGINT NOT NULL DEFAULT 0,
            value           NUMERIC(24,4),
            trade_count     INTEGER NOT NULL DEFAULT 0,
            yesterday_close NUMERIC(20,4),
            eps             NUMERIC(20,4),
            base_volume     BIGINT NOT NULL DEFAULT 0,
            fetched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            source_timestamp TIMESTAMPTZ
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_market_snapshots_instrument "
        "ON market_snapshots (instrument_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_market_snapshots_src_ts "
        "ON market_snapshots (source_timestamp)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS orderbook_events (
            id              BIGSERIAL PRIMARY KEY,
            instrument_id   VARCHAR(50) NOT NULL REFERENCES instruments(id),
            side            VARCHAR(4) NOT NULL,
            price           NUMERIC(20,4),
            volume          BIGINT NOT NULL DEFAULT 0,
            order_count     INTEGER NOT NULL DEFAULT 0,
            rank            INTEGER NOT NULL DEFAULT 0,
            fetched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_orderbook_events_instrument_side "
        "ON orderbook_events (instrument_id, side)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_ohlcv (
            id              BIGSERIAL PRIMARY KEY,
            instrument_id   VARCHAR(50) NOT NULL REFERENCES instruments(id),
            trade_date      BIGINT NOT NULL,
            open            NUMERIC(20,4),
            high            NUMERIC(20,4),
            low             NUMERIC(20,4),
            close           NUMERIC(20,4),
            volume          BIGINT NOT NULL DEFAULT 0,
            value           NUMERIC(24,4),
            trade_count     INTEGER NOT NULL DEFAULT 0,
            fetched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            source_timestamp TIMESTAMPTZ,
            CONSTRAINT uq_daily_ohlcv_instrument_date UNIQUE (instrument_id, trade_date)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_daily_ohlcv_src_ts "
        "ON daily_ohlcv (source_timestamp)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS instrument_external_ids (
            id              BIGSERIAL PRIMARY KEY,
            instrument_id   VARCHAR(50) NOT NULL REFERENCES instruments(id),
            source          VARCHAR(30) NOT NULL,
            external_id     VARCHAR(100) NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_source_external_id UNIQUE (source, external_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS symbol_aliases (
            id              BIGSERIAL PRIMARY KEY,
            instrument_id   VARCHAR(50) NOT NULL REFERENCES instruments(id),
            symbol          VARCHAR(50) NOT NULL,
            source          VARCHAR(30),
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_instrument_symbol UNIQUE (instrument_id, symbol)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS armor_raw_ingest (
            symbol      TEXT NOT NULL,
            fetched_at  TIMESTAMPTZ NOT NULL,
            payload     JSONB NOT NULL,
            PRIMARY KEY (symbol, fetched_at)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS armor_raw_ingest CASCADE")
    op.execute("DROP TABLE IF EXISTS symbol_aliases CASCADE")
    op.execute("DROP TABLE IF EXISTS instrument_external_ids CASCADE")
    op.execute("DROP TABLE IF EXISTS daily_ohlcv CASCADE")
    op.execute("DROP TABLE IF EXISTS orderbook_events CASCADE")
    op.execute("DROP TABLE IF EXISTS market_snapshots CASCADE")
    op.execute("DROP TABLE IF EXISTS trade_ticks CASCADE")
