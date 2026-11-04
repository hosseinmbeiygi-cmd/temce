"""composite (symbol, date) indexes for quotes and trades

Revision ID: 0063
Revises: 0062
Create Date: 2026-09-22

History queries (sparklines, symbol history, screener batch scans) filter by
``symbol IN (...)`` and order/filter by ``date DESC`` — but both tables only
had single-column indexes on each, so PostgreSQL picked one and scanned the
rest. ``date`` is VARCHAR(20) in this schema (see models/quote.py), so the
index works with lexicographic comparison exactly as the queries already do
(zero-dates are padded, so string ordering matches chronological ordering for
the formats written here: ``YYYY-MM-DD`` / ``YYYYMMDD``).

Additive only — ``CREATE INDEX IF NOT EXISTS`` with ``CONCURRENTLY``-safe
plain build behind the existing maintenance window; dropping is symmetrical.
"""

from alembic import op

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None

_DDL_UP = [
    "CREATE INDEX IF NOT EXISTS ix_quotes_symbol_date ON quotes (symbol, date DESC)",
    "CREATE INDEX IF NOT EXISTS ix_trades_symbol_date ON trades (symbol, date DESC)",
]

_DDL_DOWN = [
    "DROP INDEX IF EXISTS ix_trades_symbol_date",
    "DROP INDEX IF EXISTS ix_quotes_symbol_date",
]


def upgrade() -> None:
    for stmt in _DDL_UP:
        op.execute(stmt)


def downgrade() -> None:
    for stmt in _DDL_DOWN:
        op.execute(stmt)
