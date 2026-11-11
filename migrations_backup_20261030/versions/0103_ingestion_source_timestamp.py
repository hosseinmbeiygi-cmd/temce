"""Add source_timestamp columns to ingestion hot tables — audit DP-007

Revision ID: 0103
Revises: 0102
Create Date: 2026-09-27

The ingestion writers used to stamp every row only with ``fetched_at`` (the
time WE received the data). The exchange-side event time was discarded, so a
delayed poll was indistinguishable from a live tick and a late backfill could
silently overwrite fresher rows. ``StorageLayer._source_time`` now preserves
the source-provided timestamp when the parser supplies one; this migration
adds the matching nullable columns. NULL means the source did not provide an
event time (fetched_at remains authoritative for retention decisions).

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0103"
down_revision = "0102"
branch_labels = None
depends_on = None

_TABLES = ("trade_ticks", "market_snapshots", "daily_ohlcv")


def upgrade() -> None:
    conn = op.get_bind()
    for table in _TABLES:
        exists = conn.execute(
            sa.text("SELECT to_regclass(:n)"), {"n": f"public.{table}"}
        ).scalar() is not None
        if not exists:
            print(f"  - {table}: table missing — skipping source_timestamp")
            continue
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS source_timestamp TIMESTAMPTZ NULL"
        )
        # Bounded index useful for late-data reconciliation queries
        # (rows whose source clock lags the fetch clock by a lot).
        op.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{table}_src_ts "
            f"ON {table} (source_timestamp)"
        )


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP INDEX IF EXISTS idx_{table}_src_ts")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS source_timestamp")
