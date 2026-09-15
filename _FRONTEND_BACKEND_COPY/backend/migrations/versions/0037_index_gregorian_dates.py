"""Add gregorian_date indexes on the big brsapi tables

Revision ID:     0037_index_gregorian_dates
Revises:         0036_clean_historical_view
Create Date:     2026-08-11

Why
---
Date-bounded queries (last 61 days of daily history, forward-return window in
``ml/train_weight_optimizer.py``, the screener batch loader) filter on
``gregorian_date`` (DATE, Gregorian) but the existing indexes were built on
the legacy ``date`` VARCHAR (Jalali) column.  Without an index the planner
falls back to a full ``Seq Scan`` over ~12M rows, which times out scripts.

This migration adds:

  * ``idx_hist_gregorian_symbol`` on ``brsapi_historical_daily (gregorian_date, symbol)``
    — serves date-window + per-symbol lookups.
  * ``idx_snap_gregorian_symbol``  on ``brsapi_symbol_snapshots (gregorian_date, symbol)``
  * ``idx_trades_gregorian``      on ``brsapi_intraday_trades (gregorian_date)``

Indexes are created CONCURRENTLY-safe only outside a transaction; Alembic
runs in a transaction by default, so plain ``op.create_index`` is used
(acceptable for this deployment).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0037_index_gregorian_dates"
down_revision = "0036_clean_historical_view"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # brsapi_historical_daily — the hot table for screener/feature-store reads.
    op.create_index(
        "idx_hist_gregorian_symbol",
        "brsapi_historical_daily",
        [sa.text("gregorian_date"), sa.text("symbol")],
    )
    op.create_index(
        "idx_hist_gregorian",
        "brsapi_historical_daily",
        [sa.text("gregorian_date")],
    )
    # brsapi_symbol_snapshots — latest-snapshot-per-symbol lookups.
    op.create_index(
        "idx_snap_gregorian_symbol",
        "brsapi_symbol_snapshots",
        [sa.text("gregorian_date"), sa.text("symbol")],
    )
    # brsapi_intraday_trades — date-bounded trade reads.
    op.create_index(
        "idx_trades_gregorian",
        "brsapi_intraday_trades",
        [sa.text("gregorian_date")],
    )


def downgrade() -> None:
    op.drop_index("idx_trades_gregorian", table_name="brsapi_intraday_trades")
    op.drop_index("idx_snap_gregorian_symbol", table_name="brsapi_symbol_snapshots")
    op.drop_index("idx_hist_gregorian", table_name="brsapi_historical_daily")
    op.drop_index("idx_hist_gregorian_symbol", table_name="brsapi_historical_daily")
