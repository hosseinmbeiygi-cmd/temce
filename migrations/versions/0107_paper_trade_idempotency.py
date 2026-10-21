"""Paper-trade open idempotency (audit F03).

Revision ID: 0107
Revises: 0106

``PaperTradingService.open_trade`` had no idempotency key, no row lock and no
cash check, so a retried or concurrent request opened duplicate positions from
the same signal snapshot. This adds the ``idempotency_key`` column and the
partial unique index that makes one open position per (snapshot, user) the
database-enforced invariant.

The index is partial (``status = 'open'``) on purpose: a closed trade must stay
in the ledger so a later re-entry from the same snapshot is allowed.
"""

from __future__ import annotations

from alembic import op

revision: str = "0107"
down_revision: str | None = "0106"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(100)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_paper_trades_idempotency_key "
        "ON paper_trades (idempotency_key)"
    )
    # One open position per (snapshot, user). COALESCE keeps the NULL-owner
    # legacy rows comparable with each other.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_paper_trades_open_snapshot "
        "ON paper_trades (signal_snapshot_id, COALESCE(user_id, '')) "
        "WHERE status = 'open' AND signal_snapshot_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_paper_trades_open_snapshot")
    op.execute("DROP INDEX IF EXISTS ix_paper_trades_idempotency_key")
    op.execute("ALTER TABLE paper_trades DROP COLUMN IF EXISTS idempotency_key")