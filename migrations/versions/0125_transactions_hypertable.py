"""Create transactions hypertable for historical trade records (R10 migration)."""
revision = "0125"
down_revision = "0124"

import sqlalchemy as sa
from alembic import op


def upgrade():
    # R10: migrate SQLite transactions.db to TimescaleDB hypertable.
    # Trade records indexed on trade_date for efficient time-series queries.
    op.create_table(
        "transactions",
        sa.Column("symbol", sa.String(16), nullable=False, index=True),
        sa.Column("trade_date", sa.Date, nullable=False),
        sa.Column("seq_no", sa.Integer, nullable=False),
        sa.Column("time", sa.String(8), nullable=False),  # HH:MM:SS format
        sa.Column("volume", sa.Integer, nullable=False),
        sa.Column("price", sa.Float, nullable=False),
        sa.Column("is_canceled", sa.Integer, default=0, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("symbol", "trade_date", "seq_no"),
    )

    # Create hypertable on trade_date for time-series compression
    op.execute(
        """
        SELECT create_hypertable(
            'transactions',
            'trade_date',
            chunk_time_interval => INTERVAL '30 days',
            if_not_exists => TRUE
        )
        """
    )

    # Create indexes for common queries
    op.create_index("ix_transactions_symbol_date", "transactions", ["symbol", "trade_date"])
    op.create_index("ix_transactions_price", "transactions", ["price"])


def downgrade():
    # Preserve historical transaction data; full rollback is not reversible
    op.execute("DROP TABLE IF EXISTS transactions")
