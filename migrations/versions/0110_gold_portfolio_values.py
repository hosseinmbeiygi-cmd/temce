"""0110 – GoldDesk persisted portfolio value history (1 table).

Revision ID: 0110
Revises: 0109
Create Date: 2026-10-14

Why. ``/gold/portfolio`` computed P&L live from the snapshot but nothing was
persisted: without a value series there is no time-weighted return (TWR) and no
benchmark comparison against gold / USD / TEDPIX, because XIRR alone cannot be
decomposed over time. ``gold_portfolio_values`` stores one row per day with the
marked-to-market value, cost basis and the *net external cash flow* of that day
so TWR can be chained independently of deposit/withdrawal timing.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0110"
down_revision = "0109"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gold_portfolio_values",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("total_value_irt", sa.Float(), nullable=False),
        sa.Column("total_cost_irt", sa.Float(), server_default="0", nullable=False),
        # External cash flow of that day: contribution (+) / withdrawal (−).
        sa.Column("net_flow_irt", sa.Float(), server_default="0", nullable=False),
        sa.Column("unpriced_holdings", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "snapshot_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # One row per day — the series is upserted by ``as_of``.
    op.create_index(
        "uq_gold_portfolio_values_as_of",
        "gold_portfolio_values",
        ["as_of"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_gold_portfolio_values_as_of", table_name="gold_portfolio_values")
    op.drop_table("gold_portfolio_values")
