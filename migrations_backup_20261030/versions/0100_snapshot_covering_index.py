"""covering index for windowed snapshot dedup

Revision ID: 0100
Revises: 0099
Create Date: 2026-09-26

The dashboard aggregate endpoints (flow-summary, cashflow-by-sector,
asset-allocation, treemap) deduplicate ``brsapi_symbol_snapshots`` by
grouping over the last ``_SNAPSHOT_SCAN_WINDOW`` ids (see
``BrsApiQueryService.get_latest_snapshots``). That windowed GROUP BY was
still paying ~2s fetching ~23k wide rows from the heap for every cold
call. This covering index lets the planner serve the window scan
entirely from the index (measured 28ms vs 2s) — key ``id`` matches the
PK-window predicate, INCLUDE carries ``symbol`` (group key) and
``trade_value`` (sort/order key) so no heap visit is needed for the
aggregate step.

``INCLUDE`` requires PostgreSQL 11+; the project targets PostgreSQL 18
(see docker-compose / local install). Additive only — plain build
behind the maintenance window like 0063; CONCURRENTLY cannot run inside
a transactional migration. Drop is symmetrical.
"""

from alembic import op

revision = "0100"
down_revision = "0099"
branch_labels = None
depends_on = None

_DDL_UP = [
    """
    CREATE INDEX IF NOT EXISTS idx_snap_id_symbol_tv
    ON brsapi_symbol_snapshots (id) INCLUDE (symbol, trade_value)
    """,
]

_DDL_DOWN = [
    "DROP INDEX IF EXISTS idx_snap_id_symbol_tv",
]


def upgrade() -> None:
    for stmt in _DDL_UP:
        op.execute(stmt)


def downgrade() -> None:
    for stmt in _DDL_DOWN:
        op.execute(stmt)
