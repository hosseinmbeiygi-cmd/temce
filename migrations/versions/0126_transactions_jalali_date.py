"""Add Jalali date column to transactions table for audit trail."""
revision = "0126"
down_revision = "0125"

import sqlalchemy as sa
from alembic import op


def upgrade():
    # R10: preserve original Jalali dates for audit trail and reporting
    op.add_column(
        "transactions",
        sa.Column("trade_date_jalali", sa.String(10), nullable=True, index=True),
    )


def downgrade():
    op.drop_column("transactions", "trade_date_jalali")
