"""0066 – unique index on brsapi_historical_daily(symbol, date) with batched dedup.

Revision ID: 0066
Revises: 0065
Create Date: 2026-09-23

0040 deferred this table (12M+ rows, 500K+ dup groups). This migration
dedups in small batches (ctid, keep latest per group) then creates the
unique index with IF NOT EXISTS semantics so ON CONFLICT (symbol, date)
DO UPDATE in api/endpoints/brsapi.py is safe.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None

_TABLE = "brsapi_historical_daily"
_INDEX = "uq_brsapi_historical_daily_symbol_date"
_BATCH = 50_000
_MAX_BATCHES = 200


def upgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE tablename = :t AND indexname = :n"
        ),
        {"t": _TABLE, "n": _INDEX},
    ).fetchone()
    if row is not None:
        print(f"  = {_INDEX} already exists")
        return
    for i in range(_MAX_BATCHES):
        res = conn.execute(
            sa.text(
                f"DELETE FROM {_TABLE} a USING {_TABLE} b "
                f"WHERE a.ctid < b.ctid AND a.symbol = b.symbol AND a.date = b.date "
                f"AND a.ctid IN (SELECT ctid FROM {_TABLE} LIMIT {_BATCH})"
            )
        )
        print(f"  ~ dedup batch {i}: {res.rowcount} rows removed")
        if (res.rowcount or 0) == 0:
            break
    conn.execute(sa.text(f"CREATE UNIQUE INDEX {_INDEX} ON {_TABLE} (symbol, date)"))
    print(f"  + unique index {_INDEX} on {_TABLE}(symbol, date)")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(f"DROP INDEX IF EXISTS {_INDEX}"))
    print(f"  - dropped index {_INDEX}")
