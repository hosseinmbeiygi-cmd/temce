from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quotes",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("instrument_id", sa.String(50), sa.ForeignKey("instruments.id"), nullable=False, index=True),
        sa.Column("symbol", sa.String(50), nullable=True),
        sa.Column("price_close", sa.Float(), nullable=True),
        sa.Column("price_open", sa.Float(), nullable=True),
        sa.Column("price_high", sa.Float(), nullable=True),
        sa.Column("price_low", sa.Float(), nullable=True),
        sa.Column("price_last", sa.Float(), nullable=True),
        sa.Column("price_change", sa.Float(), nullable=True),
        sa.Column("price_change_pct", sa.Float(), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("trade_count", sa.Integer(), nullable=True),
        sa.Column("price_yesterday", sa.Float(), nullable=True),
        sa.Column("price_first", sa.Float(), nullable=True),
        sa.Column("price_max", sa.Float(), nullable=True),
        sa.Column("price_min", sa.Float(), nullable=True),
        sa.Column("ask_price", sa.Float(), nullable=True),
        sa.Column("ask_volume", sa.Integer(), nullable=True),
        sa.Column("bid_price", sa.Float(), nullable=True),
        sa.Column("bid_volume", sa.Integer(), nullable=True),
        sa.Column("time", sa.String(20), nullable=True),
        sa.Column("date", sa.String(20), nullable=True, index=True),
        sa.Column("timeframe", sa.String(10), nullable=True, server_default="1d"),
        sa.Column("data_source", sa.String(20), nullable=True, server_default="tsetmc"),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )
    op.create_index("ix_quotes_symbol_date", "quotes", ["symbol", "date"])
    op.create_index("ix_quotes_instrument_date", "quotes", ["instrument_id", "date"])


def downgrade() -> None:
    op.drop_index("ix_quotes_instrument_date", table_name="quotes")
    op.drop_index("ix_quotes_symbol_date", table_name="quotes")
    op.drop_table("quotes")
