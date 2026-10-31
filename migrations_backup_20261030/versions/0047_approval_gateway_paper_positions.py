"""Approval Gateway + Paper Positions + Vault key rotation.

Revision ID: 0047
Revises: 0046
Create Date: 2026-09-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0047"
down_revision: str | None = "0046"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Approval Gateway - proposals
    op.create_table(
        "proposals",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("user_id", sa.String(50), nullable=False, index=True),
        sa.Column("strategy_name", sa.String(100), nullable=False),
        sa.Column("legs", sa.Text()),
        sa.Column("price", sa.Float()),
        sa.Column("gross_cost", sa.Float()),
        sa.Column("net_cost", sa.Float()),
        sa.Column("max_loss", sa.Float()),
        sa.Column("margin", sa.Float()),
        sa.Column("var_95", sa.Float()),
        sa.Column("scenario_pnl", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("ttl_seconds", sa.Integer(), server_default="3600"),
        sa.Column("approved_by", sa.String(50)),
        sa.Column("approved_at", sa.DateTime()),
        sa.Column("reject_reason", sa.Text()),
        sa.Column("broker_order_id", sa.String(50)),
        sa.Column("calc_version", sa.String(20), server_default="v1"),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    # Approval Gateway - audit log
    op.create_table(
        "proposal_audit",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("proposal_id", sa.String(50), nullable=False, index=True),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("who", sa.String(50), nullable=False),
        sa.Column("why", sa.Text()),
        sa.Column("calc_version", sa.String(20)),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now(), index=True),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    # Paper Trading - positions ledger
    op.create_table(
        "paper_positions",
        sa.Column("symbol", sa.String(50), primary_key=True),
        sa.Column("qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_price", sa.Numeric(18, 4)),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_table(
        "paper_orders",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("proposal_id", sa.String(50)),
        sa.Column("symbol", sa.String(50), nullable=False, index=True),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open", index=True),
        sa.Column("filled_qty", sa.Integer(), server_default="0"),
        sa.Column("price", sa.Numeric(18, 4)),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table("paper_orders")
    op.drop_table("paper_positions")
    op.drop_table("proposal_audit")
    op.drop_table("proposals")
