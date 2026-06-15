from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("instrument_id", sa.String(50), sa.ForeignKey("instruments.id"), nullable=True),
        sa.Column("symbol", sa.String(50), nullable=True),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("condition", sa.Text(), nullable=True),
        sa.Column("channels", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=True, server_default=sa.text("1")),
        sa.Column("triggered_count", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("last_triggered", sa.DateTime(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "alert_history",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("alert_id", sa.String(50), sa.ForeignKey("alerts.id"), nullable=False),
        sa.Column("triggered_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column("trigger_value", sa.Float(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("delivered", sa.Boolean(), nullable=True, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_table("alert_history")
    op.drop_table("alerts")
