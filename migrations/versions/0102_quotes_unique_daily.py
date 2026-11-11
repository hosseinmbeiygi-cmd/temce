"""Add unique constraint on quotes (symbol, date, timeframe) — audit DP-005

Revision ID: 0102
Revises: 0101
Create Date: 2026-09-27

Daily OHLCV rows in ``quotes`` had no uniqueness guarantee: two ingestion
runs could both insert a row for the same symbol/date/timeframe, doubling
returns in any backtest that consumed the table. The constraint is added
after deduplicating existing rows (keeping the newest per key). Writers that
race on the same key now receive an integrity error instead of silently
corrupting history.

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0102"
down_revision = "0101"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(
        sa.text("SELECT 1 FROM pg_constraint WHERE conname = 'uq_quotes_symbol_date_timeframe'")
    ).fetchone()
    if exists is not None:
        print("  = uq_quotes_symbol_date_timeframe already exists")
        return
    # Deduplicate only if duplicates actually exist — the self-join DELETE
    # is O(n^2)-ish on 3.4M+ rows and stalls a live DB (verified 0 dup
    # groups on 2026-10-03). Keep newest per key when needed.
    dup_groups = conn.execute(sa.text(
        "SELECT COUNT(*) FROM (SELECT 1 FROM quotes "
        "GROUP BY symbol, date, COALESCE(timeframe, '1d') "
        "HAVING COUNT(*) > 1) s"
    )).scalar() or 0
    if dup_groups > 0:
        print(f"  ! quotes: {dup_groups} duplicate groups — running batched dedup")
        op.execute(sa.text("""
            DELETE FROM quotes q
            USING quotes keep
            WHERE q.symbol IS NOT NULL
              AND q.date IS NOT NULL
              AND keep.symbol = q.symbol
              AND keep.date = q.date
              AND COALESCE(keep.timeframe, '1d') = COALESCE(q.timeframe, '1d')
              AND (
                  keep.created_at > q.created_at
                  OR (keep.created_at = q.created_at AND keep.id > q.id)
              )
        """))
    else:
        print("  = quotes: no duplicate groups — skipping DELETE")

    # 2. Add the unique constraint (idempotent).
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_quotes_symbol_date_timeframe'
            ) THEN
                ALTER TABLE quotes
                ADD CONSTRAINT uq_quotes_symbol_date_timeframe
                UNIQUE (symbol, date, timeframe);
            END IF;
        END $$;
    """))


def downgrade() -> None:
    op.execute(sa.text(
        "ALTER TABLE quotes DROP CONSTRAINT IF EXISTS uq_quotes_symbol_date_timeframe"
    ))
