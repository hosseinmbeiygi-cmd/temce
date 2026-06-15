from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("symbol", sa.String(50), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("isin", sa.String(50), nullable=True, unique=True),
        sa.Column("market_type", sa.String(20), nullable=True),
        sa.Column("asset_class", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=True, server_default="active"),
        sa.Column("sector_code", sa.String(20), nullable=True),
        sa.Column("group_code", sa.String(20), nullable=True),
        sa.Column("sub_group_code", sa.String(20), nullable=True),
        sa.Column("tick_size", sa.Float(), nullable=True, server_default="1.0"),
        sa.Column("lot_size", sa.Integer(), nullable=True, server_default="1"),
        sa.Column("par_value", sa.Integer(), nullable=True, server_default="1000"),
        sa.Column("eps", sa.Float(), nullable=True, server_default="0"),
        sa.Column("shares_count", sa.BigInteger(), nullable=True, server_default="0"),
        sa.Column("base_volume", sa.BigInteger(), nullable=True, server_default="0"),
        sa.Column("market_id", sa.String(50), nullable=True),
        sa.Column("exchange_code", sa.String(20), nullable=True),
        sa.Column("board_code", sa.String(20), nullable=True),
        sa.Column("data_source", sa.String(20), nullable=True, server_default="tsetmc"),
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column("metadata_", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_instruments_symbol", "instruments", ["symbol"])
    op.create_index("ix_instruments_isin", "instruments", ["isin"])


def downgrade() -> None:
    op.drop_index("ix_instruments_isin", table_name="instruments")
    op.drop_index("ix_instruments_symbol", table_name="instruments")
    op.drop_table("instruments")
