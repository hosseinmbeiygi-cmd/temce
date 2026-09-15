"""BrsApi daily usage table for the admin usage report

Revision ID:     0039_brsapi_daily_usage
Revises:         0038_hist_symbol_gregorian_index
Create Date:     2026-08-13

One row per Tehran day aggregating live BrsApi request usage (count + 302
blocks) so the admin panel can show a historical daily-usage report
(``GET /api/v1/brsapi/manage/usage``).  Written incrementally by
``brsapi.usage_recorder.BrsApiUsageRecorder`` via an additive
``ON CONFLICT (usage_date) DO UPDATE`` upsert — safe under multiple API
workers because each process adds its own counters to the shared row.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0039_brsapi_daily_usage"
down_revision = "0038_hist_symbol_gregorian_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "brsapi_daily_usage",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("usage_date", sa.String(10), nullable=False, comment="Tehran date YYYY-MM-DD"),
        sa.Column(
            "request_count", sa.Integer(), nullable=True, server_default="0", comment="Granted live requests that day"
        ),
        sa.Column("daily_limit", sa.Integer(), nullable=True, comment="Configured daily cap in effect"),
        sa.Column(
            "blocked_count",
            sa.Integer(),
            nullable=True,
            server_default="0",
            comment="HTTP 302 over-quota blocks observed",
        ),
        sa.Column("blocked_at", sa.DateTime(), nullable=True, comment="Last 302 block timestamp"),
        sa.Column("last_request_at", sa.DateTime(), nullable=True, comment="Last granted request timestamp"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_brsapi_daily_usage_date", "brsapi_daily_usage", ["usage_date"], unique=True)
    op.create_index("idx_brsapi_daily_usage_updated", "brsapi_daily_usage", ["updated_at"])


def downgrade() -> None:
    op.drop_index("idx_brsapi_daily_usage_updated", table_name="brsapi_daily_usage")
    op.drop_index("uq_brsapi_daily_usage_date", table_name="brsapi_daily_usage")
    op.drop_table("brsapi_daily_usage")
