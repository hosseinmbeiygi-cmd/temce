"""Alert evaluation covering indexes (additive).

Revision ID: 0105
Revises: 0104

Supports the batched EvaluateAlertsJob path:
  1. ix_snapshots_symbol_fetched — symbol-filtered DISTINCT ON latest snapshot
  2. ix_quotes_symbol_date       — single window-function history fetch
  3. ix_gold_rules_enabled       — enabled-rules scan in gold_desk engine

NOTE: plain CREATE INDEX (not CONCURRENTLY) because this env runs
migrations inside a transaction. For zero-downtime deploy on a large
production table, run the CONCURRENTLY variants manually out-of-band.
"""

from __future__ import annotations

from alembic import op

revision: str = "0105"
down_revision: str | None = "0104"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_snapshots_symbol_fetched "
        "ON brsapi_symbol_snapshots (symbol, fetched_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_quotes_symbol_date "
        "ON quotes (symbol, date DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_gold_rules_enabled "
        "ON gold_alert_rules (enabled)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_gold_rules_enabled")
    op.execute("DROP INDEX IF EXISTS ix_quotes_symbol_date")
    op.execute("DROP INDEX IF EXISTS ix_snapshots_symbol_fetched")
