"""Add saved_filters table for user-saved screener presets.

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-26
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_filters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(50), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("filters_json", sa.Text(), nullable=False),
        sa.Column("logic", sa.String(10), nullable=False, server_default=sa.text("'and'")),
        sa.Column("sort_by", sa.String(50), nullable=False, server_default=sa.text("'smc_score'")),
        sa.Column("sort_order", sa.String(10), nullable=False, server_default=sa.text("'desc'")),
        sa.Column("market", sa.String(50), nullable=True),
        sa.Column("min_score", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_saved_filters_user_id", "saved_filters", ["user_id"])
    op.create_index("ix_saved_filters_user_default", "saved_filters", ["user_id", "is_default"])


def downgrade() -> None:
    op.drop_index("ix_saved_filters_user_default", "saved_filters")
    op.drop_index("ix_saved_filters_user_id", "saved_filters")
    op.drop_table("saved_filters")
