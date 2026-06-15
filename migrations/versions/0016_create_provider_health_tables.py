from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_health",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("provider", sa.String(100), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=True, server_default="unknown"),
        sa.Column("latency_ms", sa.Float(), nullable=True, server_default="0"),
        sa.Column("last_success", sa.DateTime(), nullable=True),
        sa.Column("last_failure", sa.DateTime(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("uptime_pct", sa.Float(), nullable=True, server_default="100"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "provider_health_history",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("provider_health_history")
    op.drop_table("provider_health")
