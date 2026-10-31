"""Reference DB: contracts + market_snapshots.

Revision ID: 0046
Revises: 0045
Create Date: 2026-09-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0046"
down_revision: str | None = "0045"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "contracts",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("instrument_id", sa.String(50), sa.ForeignKey("instruments.id"), nullable=False, index=True),
        sa.Column("symbol", sa.String(50), nullable=False, index=True),
        sa.Column("asset_class", sa.String(20), index=True),
        sa.Column("contract_type", sa.String(20), index=True),
        sa.Column("expiry", sa.Date(), index=True),
        sa.Column("strike", sa.Numeric(18, 4)),
        sa.Column("lot_size", sa.Integer(), server_default="1000"),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_table(
        "market_snapshots",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("contract_id", sa.String(50), sa.ForeignKey("contracts.id"), nullable=False, index=True),
        sa.Column("ts", sa.DateTime(), nullable=False, index=True),
        sa.Column("price", sa.Numeric(18, 4)),
        sa.Column("volume", sa.BigInteger()),
        sa.Column("oi", sa.BigInteger()),
        sa.Column("bid", sa.Numeric(18, 4)),
        sa.Column("ask", sa.Numeric(18, 4)),
        sa.Column("bid_volume", sa.BigInteger()),
        sa.Column("ask_volume", sa.BigInteger()),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("quality_score", sa.Float(), default=1.0),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("ix_market_snapshot_contract_ts", "market_snapshots", ["contract_id", "ts"])


def downgrade() -> None:
    op.drop_index("ix_market_snapshot_contract_ts", table_name="market_snapshots")
    op.drop_table("market_snapshots")
    op.drop_table("contracts")
