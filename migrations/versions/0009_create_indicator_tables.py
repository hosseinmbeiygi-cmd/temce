from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "indicators",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("instrument_id", sa.String(50), sa.ForeignKey("instruments.id"), nullable=False, index=True),
        sa.Column("symbol", sa.String(50), nullable=True),
        sa.Column("indicator_type", sa.String(50), nullable=False, index=True),
        sa.Column("params", sa.Text(), nullable=True),
        sa.Column("values", sa.Text(), nullable=True),
        sa.Column("timeframe", sa.String(10), nullable=True, server_default="1d"),
        sa.Column("date", sa.String(20), nullable=True),
        sa.Column("data_source", sa.String(20), nullable=True, server_default="system"),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )
    op.create_index("ix_indicators_type_symbol", "indicators", ["indicator_type", "symbol"])


def downgrade() -> None:
    op.drop_index("ix_indicators_type_symbol", table_name="indicators")
    op.drop_table("indicators")
