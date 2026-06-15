from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "codal_reports",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("symbol", sa.String(50), nullable=True, index=True),
        sa.Column("company_name", sa.String(200), nullable=True),
        sa.Column("isin", sa.String(50), nullable=True),
        sa.Column("report_type", sa.String(50), nullable=True),
        sa.Column("fiscal_year", sa.String(20), nullable=True),
        sa.Column("period", sa.String(50), nullable=True),
        sa.Column("audit_status", sa.String(20), nullable=True),
        sa.Column("publish_date", sa.String(20), nullable=True),
        sa.Column("attachment_url", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("data_source", sa.String(20), nullable=True, server_default="codal"),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )
    op.create_index("ix_codal_isin", "codal_reports", ["isin"])
    op.create_index("ix_codal_report_type", "codal_reports", ["report_type"])


def downgrade() -> None:
    op.drop_index("ix_codal_report_type", table_name="codal_reports")
    op.drop_index("ix_codal_isin", table_name="codal_reports")
    op.drop_table("codal_reports")
