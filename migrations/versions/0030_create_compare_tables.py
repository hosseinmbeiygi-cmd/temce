"""create compare_results table for storing strategy comparison history

Revision ID: 0030
Revises: 0029
Create Date: 2026-07-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "compare_results",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("symbol", sa.String(50), nullable=False, index=True),
        sa.Column("total_strategies", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("successful", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("best", sa.String(100), nullable=True),
        sa.Column("worst", sa.String(100), nullable=True),
        sa.Column("results_json", sa.Text(), nullable=True),
        sa.Column("best_return_pct", sa.Float(), nullable=True),
        sa.Column("worst_return_pct", sa.Float(), nullable=True),
        sa.Column("avg_return_pct", sa.Float(), nullable=True),
        sa.Column("start_date", sa.String(20), nullable=True),
        sa.Column("end_date", sa.String(20), nullable=True),
        sa.Column("capital", sa.Float(), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )
    op.create_index("ix_compare_results_created_at", "compare_results", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_compare_results_created_at", table_name="compare_results")
    op.drop_table("compare_results")
