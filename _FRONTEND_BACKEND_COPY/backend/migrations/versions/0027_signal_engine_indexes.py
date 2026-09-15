"""Add indexes for the multi-market signal engine's hot ORDER BY queries.

The stock generator sorts ``brsapi_symbol_snapshots`` by ``trade_value``
(LIMIT 100) and the options generator sorts ``brsapi_option_snapshots`` by
``trade_volume`` (LIMIT 200). Without matching indexes Postgres seq-scans the
836K / 375K row tables, which made the signal pipeline's stage-1 take 40-50s.

Plain CREATE INDEX (not CONCURRENTLY) because alembic runs inside a
transaction on this project's setup — same pattern as 0026.

Revision ID: 0027_signal_engine_indexes
Revises: 0026_funds_etf_indexes
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0027_signal_engine_indexes"
down_revision = "0026_funds_etf_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    # Skip if a previous partial run already created them.
    created = {
        r[0]
        for r in conn.execute(
            text(
                "SELECT indexname FROM pg_indexes WHERE tablename IN "
                "('brsapi_symbol_snapshots', 'brsapi_option_snapshots')"
            )
        ).fetchall()
    }

    if "idx_snap_trade_value" not in created:
        conn.execute(
            text(
                "CREATE INDEX idx_snap_trade_value ON brsapi_symbol_snapshots (trade_value DESC) WHERE trade_value > 0"
            )
        )
        print("idx_snap_trade_value created")
    else:
        print("idx_snap_trade_value already exists — skipped")

    if "idx_option_trade_volume" not in created:
        conn.execute(
            text(
                "CREATE INDEX idx_option_trade_volume "
                "ON brsapi_option_snapshots (trade_volume DESC) "
                "WHERE trade_volume > 0"
            )
        )
        print("idx_option_trade_volume created")
    else:
        print("idx_option_trade_volume already exists — skipped")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP INDEX IF EXISTS idx_option_trade_volume"))
    conn.execute(text("DROP INDEX IF EXISTS idx_snap_trade_value"))
