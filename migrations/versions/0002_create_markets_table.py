from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "markets",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("market_type", sa.String(20), nullable=True),
        sa.Column("exchange_code", sa.String(20), nullable=True),
        sa.Column("country", sa.String(50), nullable=True, server_default="IR"),
        sa.Column("timezone", sa.String(50), nullable=True, server_default="Asia/Tehran"),
        sa.Column("open_time", sa.String(10), nullable=True, server_default="09:00"),
        sa.Column("close_time", sa.String(10), nullable=True, server_default="12:30"),
        sa.Column("status", sa.String(20), nullable=True, server_default="active"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("markets")
