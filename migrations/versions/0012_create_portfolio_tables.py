from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolios",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("initial_capital", sa.Float(), nullable=True, server_default="0"),
        sa.Column("current_value", sa.Float(), nullable=True, server_default="0"),
        sa.Column("currency", sa.String(10), nullable=True, server_default="IRR"),
        sa.Column("owner", sa.String(100), nullable=True, server_default="system"),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "portfolio_positions",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("portfolio_id", sa.String(50), sa.ForeignKey("portfolios.id"), nullable=False),
        sa.Column("instrument_id", sa.String(50), sa.ForeignKey("instruments.id"), nullable=True),
        sa.Column("symbol", sa.String(50), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("avg_cost", sa.Float(), nullable=True),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("market_value", sa.Float(), nullable=True),
        sa.Column("unrealized_pnl", sa.Float(), nullable=True),
        sa.Column("weight_pct", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("portfolio_positions")
    op.drop_table("portfolios")
