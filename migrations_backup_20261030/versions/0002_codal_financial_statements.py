"""Add codal_financial_statements table for parsed financial statement data

Revision ID: 0002
Revises: 0001
"""

import contextlib

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS codal_financial_statements (
            id VARCHAR(50) PRIMARY KEY,
            symbol VARCHAR(50) NOT NULL,
            report_type VARCHAR(20),
            report_date VARCHAR(20),
            filename VARCHAR(200),
            file_path TEXT,
            title TEXT,
            parsed_data JSONB,
            table_count INTEGER DEFAULT 0,
            row_count INTEGER DEFAULT 0,
            import_batch VARCHAR(50),
            imported_at TIMESTAMP DEFAULT NOW(),
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_cfs_symbol ON codal_financial_statements (symbol)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_cfs_report_type ON codal_financial_statements (report_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_cfs_report_date ON codal_financial_statements (report_date)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_cfs_import_batch ON codal_financial_statements (import_batch)")
    with contextlib.suppress(Exception):
        op.execute("""
            ALTER TABLE codal_financial_statements
            ADD CONSTRAINT uq_codal_financial_symbol_type_date
            UNIQUE (symbol, report_type, report_date)
        """)


def downgrade() -> None:
    op.drop_table("codal_financial_statements")
