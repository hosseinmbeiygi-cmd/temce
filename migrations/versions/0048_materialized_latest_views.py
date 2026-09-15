"""Materialized views for latest-per-symbol queries (Q1 P0).

Revision ID: 0048
Revises: 0047
Create Date: 2026-09-09

Replaces expensive DISTINCT ON / window queries on
brsapi_symbol_snapshots (~836K rows) and symbol_snapshots
with refreshable materialized views.

- mv_latest_brsapi_symbol_snapshot : one row per symbol (latest by id)
- mv_latest_symbol_snapshot         : one row per symbol_id (latest by time)
- Unique indexes enable CONCURRENT refresh (no lock on reads).
- Helper function refresh_latest_views() for cron/worker.

See docs: apps/api/endpoints/funds.py _load_merged_funds / _get_cached_funds
"""

from __future__ import annotations

from alembic import op

revision: str = "0048"
down_revision: str | None = "0047"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # --- mv_latest_brsapi_symbol_snapshot ---
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_latest_brsapi_symbol_snapshot AS
        SELECT DISTINCT ON (symbol) *
        FROM brsapi_symbol_snapshots
        ORDER BY symbol, id DESC;
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_latest_brsapi_symbol_snapshot_symbol
        ON mv_latest_brsapi_symbol_snapshot (symbol);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_mv_latest_brsapi_snapshot_isin
        ON mv_latest_brsapi_symbol_snapshot (isin);
    """)

    # --- mv_latest_symbol_snapshot (canonical symbols) ---
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_latest_symbol_snapshot AS
        SELECT DISTINCT ON (symbol_id) *
        FROM symbol_snapshots
        ORDER BY symbol_id, time DESC;
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_latest_symbol_snapshot_symbol_id
        ON mv_latest_symbol_snapshot (symbol_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_mv_latest_symbol_snapshot_time
        ON mv_latest_symbol_snapshot (time DESC);
    """)

    # --- Refresh helper (concurrent, no read lock) ---
    op.execute("""
        CREATE OR REPLACE FUNCTION refresh_latest_views()
        RETURNS void LANGUAGE plpgsql AS $$
        BEGIN
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_latest_brsapi_symbol_snapshot;
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_latest_symbol_snapshot;
        END; $$;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS refresh_latest_views();")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_latest_symbol_snapshot;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_latest_brsapi_symbol_snapshot;")
