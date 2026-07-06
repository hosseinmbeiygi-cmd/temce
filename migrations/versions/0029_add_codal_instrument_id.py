"""add instrument_id column to codal_reports

Revision ID: 0029
Revises: 0028
Create Date: 2026-07-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("codal_reports", sa.Column("instrument_id", sa.String(50), nullable=True))
    op.create_index("ix_codal_reports_instrument_id", "codal_reports", ["instrument_id"])
    # Backfill instrument_id from symbol
    op.execute("UPDATE codal_reports SET instrument_id = symbol WHERE instrument_id IS NULL")


def downgrade() -> None:
    op.drop_index("ix_codal_reports_instrument_id", table_name="codal_reports")
    op.drop_column("codal_reports", "instrument_id")
