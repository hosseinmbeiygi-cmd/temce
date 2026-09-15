"""Add sector index on brsapi_symbol_snapshots for fast fund queries.

The /funds API now merges TSE ETF snapshots (sector = 'صندوق سرمایه‌گذاری
قابل معامله') from brsapi_symbol_snapshots (~836K rows). Without an index on
``sector`` the query does a full sequential scan which makes the endpoint
time out. This migration adds:

  - idx_snap_sector      on brsapi_symbol_snapshots (sector)
  - idx_ime_fund_symbol  on brsapi_ime_funds (symbol)

Both are cheap btree indexes created CONCURRENTLY-safe (no concurrent flag
here because alembic runs inside a transaction on this project's setup;
plain CREATE INDEX is fine for a personal system).

Revision ID: 0026_funds_etf_indexes
Revises: 0025_add_dual_date_columns
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0026_funds_etf_indexes"
down_revision = "0025_add_dual_date_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    # Skip if a previous partial run already created them.
    created = {
        r[0]
        for r in conn.execute(
            text("SELECT indexname FROM pg_indexes WHERE tablename IN ('brsapi_symbol_snapshots', 'brsapi_ime_funds')")
        ).fetchall()
    }

    if "idx_snap_sector" not in created:
        conn.execute(text("CREATE INDEX idx_snap_sector ON brsapi_symbol_snapshots (sector)"))
        print("idx_snap_sector created")
    else:
        print("idx_snap_sector already exists — skipped")

    if "idx_ime_fund_symbol" not in created:
        conn.execute(text("CREATE INDEX idx_ime_fund_symbol ON brsapi_ime_funds (symbol)"))
        print("idx_ime_fund_symbol created")
    else:
        print("idx_ime_fund_symbol already exists — skipped")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP INDEX IF EXISTS idx_ime_fund_symbol"))
    conn.execute(text("DROP INDEX IF EXISTS idx_snap_sector"))
