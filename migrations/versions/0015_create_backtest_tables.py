from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("strategy_type", sa.String(100), nullable=True),
        sa.Column("symbols", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=True, server_default="queued"),
        sa.Column("start_date", sa.String(20), nullable=True),
        sa.Column("end_date", sa.String(20), nullable=True),
        sa.Column("initial_capital", sa.Float(), nullable=True),
        sa.Column("current_value", sa.Float(), nullable=True),
        sa.Column("total_return_pct", sa.Float(), nullable=True),
        sa.Column("commission_pct", sa.Float(), nullable=True, server_default="0.0035"),
        sa.Column("slippage_bps", sa.Float(), nullable=True, server_default="10"),
        sa.Column("strategy_params", sa.Text(), nullable=True),
        sa.Column("metrics", sa.Text(), nullable=True),
        sa.Column("progress_pct", sa.Float(), nullable=True, server_default="0"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(100), nullable=True, server_default="system"),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )
    op.create_table(
        "backtest_trades",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("run_id", sa.String(50), sa.ForeignKey("backtest_runs.id"), nullable=False),
        sa.Column("symbol", sa.String(50), nullable=True),
        sa.Column("direction", sa.String(10), nullable=True),
        sa.Column("entry_date", sa.String(20), nullable=True),
        sa.Column("exit_date", sa.String(20), nullable=True),
        sa.Column("entry_price", sa.Float(), nullable=True),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("gross_profit", sa.Float(), nullable=True),
        sa.Column("net_profit", sa.Float(), nullable=True),
        sa.Column("return_pct", sa.Float(), nullable=True),
        sa.Column("commission", sa.Float(), nullable=True),
        sa.Column("exit_reason", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("backtest_trades")
    op.drop_table("backtest_runs")
