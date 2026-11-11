"""per-user ownership for the paper-trading ledger

Revision ID: 0064
Revises: 0063
Create Date: 2026-09-22

``paper_trades`` was a shared book: any authenticated user could open/close
trades and read everyone's P&L. This revision adds a ``user_id`` column
(nullable for legacy rows) plus an index for the owner-scoped queries the
service now issues. NULL rows keep their pre-isolation meaning: part of the
shared demo ledger, visible read-only to everyone.

Additive only — no existing row is rewritten and re-running is harmless.
"""

from alembic import op

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None

_DDL_UP = [
    "ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS user_id VARCHAR(50)",
    "CREATE INDEX IF NOT EXISTS ix_paper_trades_user_id ON paper_trades (user_id)",
]

_DDL_DOWN = [
    "DROP INDEX IF EXISTS ix_paper_trades_user_id",
    "ALTER TABLE paper_trades DROP COLUMN IF EXISTS user_id",
]


def upgrade() -> None:
    for stmt in _DDL_UP:
        op.execute(stmt)


def downgrade() -> None:
    for stmt in _DDL_DOWN:
        op.execute(stmt)
