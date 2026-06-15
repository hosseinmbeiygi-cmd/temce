from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trades",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("instrument_id", sa.String(50), sa.ForeignKey("instruments.id"), nullable=False, index=True),
        sa.Column("symbol", sa.String(50), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("volume", sa.Integer(), nullable=True),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("side", sa.String(10), nullable=True),
        sa.Column("time", sa.String(20), nullable=True),
        sa.Column("date", sa.String(20), nullable=True, index=True),
        sa.Column("data_source", sa.String(20), nullable=True, server_default="tsetmc"),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )
    op.create_index("ix_trades_symbol_date", "trades", ["symbol", "date"])


def downgrade() -> None:
    op.drop_index("ix_trades_symbol_date", table_name="trades")
    op.drop_table("trades")
