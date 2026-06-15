from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "macro_indicators",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("indicator", sa.String(100), nullable=False, index=True),
        sa.Column("country", sa.String(50), nullable=True, server_default="iran"),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("previous_value", sa.Float(), nullable=True),
        sa.Column("change_pct", sa.Float(), nullable=True),
        sa.Column("date", sa.String(20), nullable=True, index=True),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("frequency", sa.String(20), nullable=True, server_default="monthly"),
        sa.Column("data_source", sa.String(20), nullable=True, server_default="rss"),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )
    op.create_index("ix_macro_indicator_date", "macro_indicators", ["indicator", "date"])


def downgrade() -> None:
    op.drop_index("ix_macro_indicator_date", table_name="macro_indicators")
    op.drop_table("macro_indicators")
