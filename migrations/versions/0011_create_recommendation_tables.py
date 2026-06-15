from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recommendations",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("instrument_id", sa.String(50), sa.ForeignKey("instruments.id"), nullable=True),
        sa.Column("symbol", sa.String(50), nullable=False, index=True),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True, server_default="0"),
        sa.Column("target_price", sa.Float(), nullable=True),
        sa.Column("stop_loss", sa.Float(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("strategy", sa.String(50), nullable=True),
        sa.Column("risk_level", sa.String(20), nullable=True),
        sa.Column("horizon", sa.String(20), nullable=True),
        sa.Column("data_source", sa.String(20), nullable=True, server_default="system"),
        sa.Column("generated_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )
    op.create_index("ix_recommendations_symbol", "recommendations", ["symbol"])


def downgrade() -> None:
    op.drop_index("ix_recommendations_symbol", table_name="recommendations")
    op.drop_table("recommendations")
