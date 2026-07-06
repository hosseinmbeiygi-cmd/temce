"""
BrsApi — Create 3 Missing Tables
==================================

Migration version: 0024
Revision ID:      0024
Revises:          0023

Creates 3 tables that are defined in the ORM models but were never
created in the database by previous migrations:

- ``brsapi_gold_coin_history``   — Historical gold & coin prices
- ``brsapi_currency_24h``        — 24-hour currency changes
- ``brsapi_gold_24h``            — 24-hour gold price changes
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | None = None
depends_on: str | None = None


def _create_gold_coin_history() -> None:
    op.create_table(
        "brsapi_gold_coin_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("date", sa.String(20), nullable=False),
        sa.Column("price_open", sa.Float(), nullable=True),
        sa.Column("price_high", sa.Float(), nullable=True),
        sa.Column("price_low", sa.Float(), nullable=True),
        sa.Column("price_close", sa.Float(), nullable=True),
        sa.Column("fetched_at", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_gold_hist_symbol_date", "brsapi_gold_coin_history", ["symbol", "date"])
    op.add_column("brsapi_gold_coin_history", sa.Column("ins_id", sa.String(50), nullable=True))
    op.add_column("brsapi_gold_coin_history", sa.Column("instrument_id", sa.String(50), nullable=True))
    op.create_index("idx_gold_coin_history_mig_ins_id", "brsapi_gold_coin_history", ["ins_id"])
    op.create_index("idx_gold_coin_history_mig_instr", "brsapi_gold_coin_history", ["instrument_id"])


def _create_currency_24h() -> None:
    op.create_table(
        "brsapi_currency_24h",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("price_now", sa.Float(), nullable=True),
        sa.Column("price_24h_ago", sa.Float(), nullable=True),
        sa.Column("change_value", sa.Float(), nullable=True),
        sa.Column("change_percent", sa.Float(), nullable=True),
        sa.Column("high_24h", sa.Float(), nullable=True),
        sa.Column("low_24h", sa.Float(), nullable=True),
        sa.Column("date", sa.String(20), nullable=True),
        sa.Column("time", sa.String(20), nullable=True),
        sa.Column("fetched_at", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_currency_24h_symbol", "brsapi_currency_24h", ["symbol"])
    op.add_column("brsapi_currency_24h", sa.Column("ins_id", sa.String(50), nullable=True))
    op.add_column("brsapi_currency_24h", sa.Column("instrument_id", sa.String(50), nullable=True))
    op.create_index("idx_currency_24h_mig_ins_id", "brsapi_currency_24h", ["ins_id"])
    op.create_index("idx_currency_24h_mig_instr", "brsapi_currency_24h", ["instrument_id"])


def _create_gold_24h() -> None:
    op.create_table(
        "brsapi_gold_24h",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("price_now", sa.Float(), nullable=True),
        sa.Column("price_24h_ago", sa.Float(), nullable=True),
        sa.Column("change_value", sa.Float(), nullable=True),
        sa.Column("change_percent", sa.Float(), nullable=True),
        sa.Column("high_24h", sa.Float(), nullable=True),
        sa.Column("low_24h", sa.Float(), nullable=True),
        sa.Column("date", sa.String(20), nullable=True),
        sa.Column("time", sa.String(20), nullable=True),
        sa.Column("fetched_at", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_gold_24h_symbol", "brsapi_gold_24h", ["symbol"])
    op.add_column("brsapi_gold_24h", sa.Column("ins_id", sa.String(50), nullable=True))
    op.add_column("brsapi_gold_24h", sa.Column("instrument_id", sa.String(50), nullable=True))
    op.create_index("idx_gold_24h_mig_ins_id", "brsapi_gold_24h", ["ins_id"])
    op.create_index("idx_gold_24h_mig_instr", "brsapi_gold_24h", ["instrument_id"])


def upgrade() -> None:
    _create_gold_coin_history()
    _create_currency_24h()
    _create_gold_24h()


def downgrade() -> None:
    op.drop_table("brsapi_gold_24h", if_exists=True)
    op.drop_table("brsapi_currency_24h", if_exists=True)
    op.drop_table("brsapi_gold_coin_history", if_exists=True)
