"""Paper Trading tables: signal journal + simulated trade ledger + equity curve.

Adds three tables (models already defined in ``models/paper_trading.py``):

  1. ``paper_signal_snapshots`` — full daily snapshot of every generated signal
     (all signal fields + the complete serialized payload).
  2. ``paper_trades`` — the simulated accounting ledger (entry/exit, P&L).
  3. ``paper_equity_history`` — daily equity curve of the paper account.

Revision ID: 0029_paper_trading_tables
Revises: 0028_quotes_bigint_columns
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0029_paper_trading_tables"
down_revision = "0028_quotes_bigint_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_signal_snapshots",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("batch_id", sa.String(50), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("name", sa.String(120), nullable=True),
        sa.Column("market", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("timeframe", sa.String(20), nullable=False),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("entry_zone", sa.Text(), nullable=True),
        sa.Column("stop_loss", sa.Text(), nullable=True),
        sa.Column("targets", sa.Text(), nullable=True),
        sa.Column("risk_reward", sa.Text(), nullable=True),
        sa.Column("position_sizing", sa.Text(), nullable=True),
        sa.Column("confirmation_condition", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("invalidation", sa.Text(), nullable=True),
        sa.Column("trailing_stop", sa.Text(), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("change_pct", sa.Float(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("strength", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("full_signal", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_paper_snap_batch", "paper_signal_snapshots", ["batch_id"])
    op.create_index("ix_paper_snap_symbol", "paper_signal_snapshots", ["symbol"])
    op.create_index("ix_paper_snap_market", "paper_signal_snapshots", ["market"])
    op.create_index("ix_paper_snap_direction", "paper_signal_snapshots", ["direction"])
    op.create_index("ix_paper_snap_timeframe", "paper_signal_snapshots", ["timeframe"])
    op.create_index("ix_paper_snap_generated", "paper_signal_snapshots", ["generated_at"])

    op.create_table(
        "paper_trades",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("signal_snapshot_id", sa.String(50), nullable=True),
        sa.Column("symbol", sa.String(50), nullable=False),
        sa.Column("name", sa.String(120), nullable=True),
        sa.Column("market", sa.String(20), nullable=False),
        sa.Column("timeframe", sa.String(20), nullable=False),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("stop_loss_price", sa.Float(), nullable=True),
        sa.Column("target1_price", sa.Float(), nullable=True),
        sa.Column("target2_price", sa.Float(), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=True),
        sa.Column("capital_allocated", sa.Float(), nullable=True),
        sa.Column("opened_at", sa.DateTime(), nullable=False),
        sa.Column("entry_notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("exit_reason", sa.String(30), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("exit_notes", sa.Text(), nullable=True),
        sa.Column("pnl", sa.Float(), nullable=True),
        sa.Column("pnl_pct", sa.Float(), nullable=True),
        sa.Column("holding_days", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_paper_trades_symbol", "paper_trades", ["symbol"])
    op.create_index("ix_paper_trades_market", "paper_trades", ["market"])
    op.create_index("ix_paper_trades_status", "paper_trades", ["status"])
    op.create_index("ix_paper_trades_opened", "paper_trades", ["opened_at"])
    op.create_index("ix_paper_trades_closed", "paper_trades", ["closed_at"])
    op.create_index("ix_paper_trades_snapshot", "paper_trades", ["signal_snapshot_id"])

    op.create_table(
        "paper_equity_history",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("date", sa.String(10), nullable=False),
        sa.Column("equity", sa.Float(), nullable=False),
        sa.Column("cash", sa.Float(), nullable=True),
        sa.Column("open_value", sa.Float(), nullable=True),
        sa.Column("realized_pnl", sa.Float(), nullable=True),
        sa.Column("open_positions", sa.Integer(), nullable=True),
        sa.Column("total_closed", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_paper_equity_date", "paper_equity_history", ["date"])


def downgrade() -> None:
    op.drop_table("paper_equity_history")
    op.drop_table("paper_trades")
    op.drop_table("paper_signal_snapshots")
