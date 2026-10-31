"""0042 – GoldDesk Portfolio (3 tables).

Revision ID: 0042
Revises: 0041
Create Date: 2026-08-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0042_gold_portfolio"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── gold_holdings (هر خط = یک خرید) ──────────────────────
    op.create_table(
        "gold_holdings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(32), nullable=False, index=True),
        sa.Column("display_name", sa.String(64), nullable=False),
        sa.Column("vehicle", sa.String(16), server_default="etf"),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("buy_price", sa.Float(), nullable=False),
        sa.Column("buy_amount_irt", sa.Float(), nullable=False),
        sa.Column("buy_fee_pct", sa.Float(), server_default="0"),
        sa.Column("bought_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("note", sa.String(256), nullable=True),
    )
    op.create_index("ix_holdings_symbol", "gold_holdings", ["symbol"])

    # ── gold_dca_plans (پلن‌های DCA) ──────────────────────────
    op.create_table(
        "gold_dca_plans",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("total_capital_irt", sa.Float(), nullable=False),
        sa.Column("risk_profile", sa.String(16), server_default="balanced"),
        sa.Column("vehicle", sa.String(16), server_default="etf"),
        sa.Column("ladder_json", sa.Text(), nullable=False),  # JSON array
        sa.Column("executed_tranches", sa.Integer(), server_default="0"),
        sa.Column("current_score", sa.Integer(), server_default="0"),
        sa.Column("stop_loss_pct", sa.Float(), server_default="8"),
        sa.Column("take_profit_pct", sa.Float(), server_default="25"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── gold_trades (معاملات ثبت‌شده) ─────────────────────────
    op.create_table(
        "gold_trades",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("holding_id", sa.BigInteger(), sa.ForeignKey("gold_holdings.id", ondelete="CASCADE"), nullable=True),
        sa.Column("plan_id", sa.BigInteger(), sa.ForeignKey("gold_dca_plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("action", sa.String(8), nullable=False),  # buy | sell
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("amount_irt", sa.Float(), nullable=False),
        sa.Column("fee_irt", sa.Float(), server_default="0"),
        sa.Column("pnl_irt", sa.Float(), server_default="0"),
        sa.Column("note", sa.String(256), nullable=True),
        sa.Column("traded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("gold_trades")
    op.drop_table("gold_dca_plans")
    op.drop_index("ix_holdings_symbol", table_name="gold_holdings")
    op.drop_table("gold_holdings")
