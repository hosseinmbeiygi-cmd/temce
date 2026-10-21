"""Gold feed provider health attempts.

Revision ID: 0111
Revises: 0110
Create Date: 2026-10-18

The resilient gold spot feed already reports each provider attempt in its
return payload, but nothing survived the request. ``gold_feed_health_attempts``
stores one row per provider per check so the feed-health endpoint can show the
last N attempts and the current primary status after a restart.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0111"
down_revision = "0110"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gold_feed_health_attempts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("check_id", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("age_seconds", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("idx_gold_feed_health_check", "gold_feed_health_attempts", ["check_id"])
    op.create_index(
        "idx_gold_feed_health_provider_checked",
        "gold_feed_health_attempts",
        ["provider", "checked_at"],
    )
    op.create_index("idx_gold_feed_health_checked", "gold_feed_health_attempts", ["checked_at"])


def downgrade() -> None:
    op.drop_index("idx_gold_feed_health_checked", table_name="gold_feed_health_attempts")
    op.drop_index(
        "idx_gold_feed_health_provider_checked",
        table_name="gold_feed_health_attempts",
    )
    op.drop_index("idx_gold_feed_health_check", table_name="gold_feed_health_attempts")
    op.drop_table("gold_feed_health_attempts")
