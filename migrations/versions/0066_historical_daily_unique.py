"""0066 – unique index on brsapi_historical_daily(symbol, date), guarded.

Revision ID: 0066
Revises: 0065
Create Date: 2026-09-23

0040 deferred this table: ~13.6M rows with ~5M duplicate (symbol, date)
groups (verified 2026-09-23 on local DB). A naive in-migration DELETE
would lock the table for hours, so this migration is intentionally
conservative:

- If no duplicates remain (e.g. after the offline batch dedup job below),
  it creates the unique index, making
  ``ON CONFLICT (symbol, date) DO UPDATE`` safe for this table.
- If duplicates still exist, it NO-OPs with a clear message and leaves
  the existing non-unique ``idx_hist_symbol_date`` in place. The sync
  write path (``bulk_insert`` → ``ON CONFLICT DO NOTHING``) stays safe.

Offline batch dedup job (run manually, in small chunks, off-peak)::

    DELETE FROM brsapi_historical_daily a USING brsapi_historical_daily b
    WHERE a.ctid < b.ctid
      AND a.symbol = b.symbol AND a.date = b.date
      AND a.symbol >= '<lo>' AND a.symbol < '<hi>';  -- walk symbol ranges
    -- repeat until:
    SELECT COUNT(*) FROM (SELECT 1 FROM brsapi_historical_daily
      GROUP BY symbol, date HAVING COUNT(*) > 1) s;  -- returns 0
    -- then re-run this migration (or create the index directly):
    CREATE UNIQUE INDEX CONCURRENTLY uq_brsapi_historical_daily_symbol_date
      ON brsapi_historical_daily (symbol, date);
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


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE tablename = :t AND indexname = :n"
        ),
        {"t": _TABLE, "n": _INDEX},
    ).fetchone()
    if exists is not None:
        print(f"  = {_INDEX} already exists")
        return
    dup_groups = conn.execute(
        sa.text(
            f"SELECT COUNT(*) FROM (SELECT 1 FROM {_TABLE} "
            f"GROUP BY symbol, date HAVING COUNT(*) > 1) s"
        )
    ).scalar() or 0
    if dup_groups > 0:
        print(
            f"  ! {_TABLE}: {dup_groups} duplicate (symbol, date) groups remain — "
            f"SKIPPING unique index (see 0066 docstring for the offline batch job). "
            f"Sync writes stay on ON CONFLICT DO NOTHING."
        )
        return
    conn.execute(sa.text(f"CREATE UNIQUE INDEX {_INDEX} ON {_TABLE} (symbol, date)"))
    print(f"  + unique index {_INDEX} on {_TABLE}(symbol, date)")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(f"DROP INDEX IF EXISTS {_INDEX}"))
    print(f"  - dropped index {_INDEX}")
