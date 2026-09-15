"""Add composite index for fast dashboard snapshot queries.

The dashboard live-data endpoints (``/market/heatmap``, ``/market/enriched-heatmap``,
``/market/gainers``, etc.) run a ``GROUP BY symbol ... ORDER BY MAX(trade_value) DESC``
subquery over ``brsapi_symbol_snapshots`` (800K+ rows). Without a matching index this
used a parallel seq scan and took ~14s; with ``idx_snap_sym_tv_id`` it becomes an
index-only scan and returns in <1s.

Revision ID: 0030_symbol_snapshot_dashboard_index
Revises: 0029_paper_trading_tables
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0030_symbol_snapshot_dashboard_index"
down_revision = "0029_paper_trading_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_snap_sym_tv_id",
        "brsapi_symbol_snapshots",
        ["symbol", sa.text("trade_value DESC NULLS LAST"), sa.text("id DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_snap_sym_tv_id", table_name="brsapi_symbol_snapshots")
