"""SIG-01: add target1_price, target2_price, stop_loss_price to signal_accuracy.

Revision ID: 0128
Revises: 0127
Create Date: 2026-11-16

Root cause: signal_accuracy had no columns to store the entry-time target and stop
levels, forcing _evaluate_past_signals to re-derive them with hardcoded 5%/10%/3%
percentages.  After this migration the INSERT in _persist_pending_signals stores
the signal's actual parsed target/stop prices; the evaluator then reads them
back instead of guessing.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0128"
down_revision = "0127"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = {c["name"] for c in inspector.get_columns("signal_accuracy")}

    if "target1_price" not in cols:
        op.add_column(
            "signal_accuracy",
            sa.Column("target1_price", sa.Float(), nullable=True),
        )
    if "target2_price" not in cols:
        op.add_column(
            "signal_accuracy",
            sa.Column("target2_price", sa.Float(), nullable=True),
        )
    if "stop_loss_price" not in cols:
        op.add_column(
            "signal_accuracy",
            sa.Column("stop_loss_price", sa.Float(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("signal_accuracy", "target1_price")
    op.drop_column("signal_accuracy", "target2_price")
    op.drop_column("signal_accuracy", "stop_loss_price")
