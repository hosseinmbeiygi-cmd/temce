from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signals",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("instrument_id", sa.String(50), sa.ForeignKey("instruments.id"), nullable=True),
        sa.Column("symbol", sa.String(50), nullable=False, index=True),
        sa.Column("signal_type", sa.String(30), nullable=False),
        sa.Column("strength", sa.Float(), nullable=True, server_default="0"),
        sa.Column("direction", sa.String(20), nullable=True),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("indicators", sa.Text(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("timeframe", sa.String(10), nullable=True, server_default="1d"),
        sa.Column("data_source", sa.String(20), nullable=True, server_default="system"),
        sa.Column("generated_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )
    op.create_index("ix_signals_symbol_type", "signals", ["symbol", "signal_type"])


def downgrade() -> None:
    op.drop_index("ix_signals_symbol_type", table_name="signals")
    op.drop_table("signals")
