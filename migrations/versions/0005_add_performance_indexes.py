"""Add performance indexes for quotes, trades, and instruments tables."""

revision = "0005_add_performance_indexes"
down_revision = "0004_ml_symbol_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op
    from sqlalchemy import text

    # Composite indexes on quotes for common query patterns
    op.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_quotes_instrument_date
        ON quotes (instrument_id, date DESC);
    """))
    op.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_quotes_symbol_date
        ON quotes (symbol, date DESC);
    """))

    # Composite index on trades for common query patterns
    op.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_trades_instrument_date
        ON trades (instrument_id, date DESC);
    """))

    # GIN index on instruments name for ILIKE search (pg_trgm)
    op.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
    op.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_instruments_name_trgm
        ON instruments USING gin (name gin_trgm_ops);
    """))

    # Partial index on quotes for daily timeframe lookups
    op.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_quotes_instrument_date_daily
        ON quotes (instrument_id, date DESC)
        WHERE timeframe = '1d';
    """))


def downgrade() -> None:
    from alembic import op

    op.drop_index("ix_quotes_instrument_date_daily", if_exists=True)
    op.drop_index("ix_instruments_name_trgm", if_exists=True)
    op.drop_index("ix_trades_instrument_date", if_exists=True)
    op.drop_index("ix_quotes_symbol_date", if_exists=True)
    op.drop_index("ix_quotes_instrument_date", if_exists=True)
