"""Create ml_symbol_results table for per-symbol ML training results."""

revision = "0004_ml_symbol_results"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op
    from sqlalchemy import text

    op.execute(text("""
        CREATE TABLE IF NOT EXISTS ml_symbol_results (
            id VARCHAR(50) PRIMARY KEY,
            symbol VARCHAR(50) NOT NULL,
            data_type VARCHAR(20) NOT NULL,
            model_type VARCHAR(50) NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            metrics TEXT,
            fold_metrics TEXT,
            feature_importance TEXT,
            train_samples INTEGER DEFAULT 0,
            val_samples INTEGER DEFAULT 0,
            feature_count INTEGER DEFAULT 0,
            feature_groups TEXT,
            start_date VARCHAR(20),
            end_date VARCHAR(20),
            artifact_path TEXT,
            duration_seconds FLOAT DEFAULT 0,
            error TEXT,
            trained_at TIMESTAMP DEFAULT NOW(),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """))
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_ml_symbol_results_symbol ON ml_symbol_results (symbol);"))
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_ml_symbol_results_data_type ON ml_symbol_results (data_type);"))
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_ml_symbol_results_model_type ON ml_symbol_results (model_type);"))
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_ml_symbol_results_status ON ml_symbol_results (status);"))
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_ml_symbol_results_trained_at ON ml_symbol_results (trained_at);"))
    # Unique constraint: one result per symbol + data_type + model_type
    op.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_ml_symbol_results_symbol_data_model
        ON ml_symbol_results (symbol, data_type, model_type);
    """))


def downgrade() -> None:
    from alembic import op
    op.drop_table("ml_symbol_results")
