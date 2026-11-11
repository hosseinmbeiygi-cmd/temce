"""Gold option daily IV history (1 table).

Revision ID: 0115
Revises: 0114
Create Date: 2026-10-22

Table gold_option_iv_history: per-contract implied-volatility snapshot
written daily by GoldOptionIvSnapshotJob, feeding iv_rank / iv_percentile
(STEP 5-FIX-2).  Idempotent per (symbol, as_of, strike).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0115"
down_revision = "0114"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gold_option_iv_history",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("expiry", sa.String(length=32), nullable=True),
        sa.Column("strike", sa.Float(), nullable=False),
        sa.Column("iv", sa.Float(), nullable=False),
        sa.Column("forward", sa.Float(), nullable=True),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_gold_option_iv_history_symbol",
        "gold_option_iv_history",
        ["symbol"],
        unique=False,
    )
    op.create_index(
        "ix_gold_option_iv_history_as_of",
        "gold_option_iv_history",
        ["as_of"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_gold_option_iv_history_symbol_as_of_strike",
        "gold_option_iv_history",
        ["symbol", "as_of", "strike"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_gold_option_iv_history_symbol_as_of_strike",
        "gold_option_iv_history",
        type_="unique",
    )
    op.drop_index(
        "ix_gold_option_iv_history_as_of", table_name="gold_option_iv_history"
    )
    op.drop_index(
        "ix_gold_option_iv_history_symbol", table_name="gold_option_iv_history"
    )
    op.drop_table("gold_option_iv_history")
