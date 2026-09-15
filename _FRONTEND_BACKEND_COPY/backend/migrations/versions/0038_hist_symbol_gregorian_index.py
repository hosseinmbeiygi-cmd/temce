"""Add (symbol, gregorian_date) index for per-symbol date windows

Revision ID:     0038_hist_symbol_gregorian_index
Revises:         0037_index_gregorian_dates
Create Date:     2026-08-11

The 0037 index is (gregorian_date, symbol) — great for date-window scans but
not for "latest N rows per symbol" (LATERAL) lookups, which need the symbol
as the leading column.  This migration adds the complementary index so the
screener batch loader can fetch the last 61 days *per symbol* without
pulling all ~12M rows into memory.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0038_hist_symbol_gregorian_index"
down_revision = "0037_index_gregorian_dates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_hist_symbol_gregorian",
        "brsapi_historical_daily",
        [sa.text("symbol"), sa.text("gregorian_date")],
    )


def downgrade() -> None:
    op.drop_index("idx_hist_symbol_gregorian", table_name="brsapi_historical_daily")
