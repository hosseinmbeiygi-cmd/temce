"""Gold macro indicators + CFTC COT gold positions (2 tables).

Revision ID: 0112
Revises: 0111
Create Date: 2026-10-18

Stores provenance and fetched_at per row so the gold macro posture can be fed
from stored data rather than live network calls.

Table gold_macro_indicators: FRED / external macro observations (10Y TIPS real
yield DFII10, broad dollar index DTWEXBGS). Upsert key: (indicator, as_of).
Table gold_cot_positions: weekly CFTC COT gold futures positions
(managed-money net, commercial net, weekly change, percentile). Upsert key:
report_date.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0112"
down_revision = "0111"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gold_macro_indicators",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("indicator", sa.String(length=64), nullable=False, index=True),
        sa.Column("country", sa.String(length=50), server_default="global", index=True),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("previous_value", sa.Float(), nullable=True),
        sa.Column("change_pct", sa.Float(), nullable=True),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("provenance", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("frequency", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "uq_gold_macro_indicators_as_of",
        "gold_macro_indicators",
        ["indicator", "as_of"],
        unique=True,
    )

    op.create_table(
        "gold_cot_positions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("report_date", sa.Date(), nullable=False, index=True),
        sa.Column(
            "cftc_contract_market_code",
            sa.String(length=16),
            nullable=False,
        ),
        sa.Column("market_name", sa.String(length=64), nullable=True),
        sa.Column("managed_money_long", sa.BigInteger(), nullable=True),
        sa.Column("managed_money_short", sa.BigInteger(), nullable=True),
        sa.Column("managed_money_net", sa.BigInteger(), nullable=True),
        sa.Column("managed_money_net_change", sa.BigInteger(), nullable=True),
        sa.Column("commercial_long", sa.BigInteger(), nullable=True),
        sa.Column("commercial_short", sa.BigInteger(), nullable=True),
        sa.Column("commercial_net", sa.BigInteger(), nullable=True),
        sa.Column("open_interest", sa.BigInteger(), nullable=True),
        sa.Column("managed_money_net_percentile", sa.Float(), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="CFTC"),
        sa.Column("provenance", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "uq_gold_cot_positions_report_date",
        "gold_cot_positions",
        ["report_date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_gold_cot_positions_report_date", table_name="gold_cot_positions")
    op.drop_table("gold_cot_positions")
    op.drop_index("uq_gold_macro_indicators_as_of", table_name="gold_macro_indicators")
    op.drop_table("gold_macro_indicators")
