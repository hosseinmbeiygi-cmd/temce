"""GoldDesk futures / kill-switch / portfolio-journal tables.

Revision ID: 0114
Revises: 0113
Create Date: 2026-10-21

``models/gold.py`` has declared ``gold_futures_positions``,
``gold_kill_switch_events`` and ``gold_portfolio_holdings`` since the GoldDesk
bundle landed, but no migration ever created them — every request against the
futures and portfolio-journal endpoints failed with
``UndefinedTableError: relation "gold_futures_positions" does not exist``.
The tables are created defensively so a database that already grew them
out-of-band is left untouched.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0114"
down_revision = "0113"
branch_labels = None
depends_on = None

FUTURES = "gold_futures_positions"
KILL_SWITCH = "gold_kill_switch_events"
HOLDINGS = "gold_portfolio_holdings"


def _existing() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    existing = _existing()

    # ── gold_futures_positions ──────────────────────────────────
    if FUTURES not in existing:
        op.create_table(
            FUTURES,
            sa.Column("id", sa.String(50), primary_key=True),
            sa.Column("contract_symbol", sa.String(50), nullable=False, index=True),
            sa.Column("position_type", sa.String(10), nullable=False),
            sa.Column("leverage", sa.Integer(), nullable=False, server_default="10"),
            sa.Column("entry_price", sa.Float(), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("initial_margin", sa.Float(), nullable=False),
            sa.Column("maintenance_margin", sa.Float(), nullable=False),
            sa.Column("liquidation_price", sa.Float(), nullable=False),
            sa.Column("opened_at", sa.DateTime(), nullable=False, index=True),
            sa.Column("entry_notes", sa.Text(), nullable=True),
            sa.Column("stop_loss", sa.Float(), nullable=True),
            sa.Column("target_1", sa.Float(), nullable=True),
            sa.Column("target_2", sa.Float(), nullable=True),
            sa.Column("current_price", sa.Float(), nullable=True),
            sa.Column("last_price_update", sa.DateTime(), nullable=True),
            sa.Column("unrealized_pnl", sa.Float(), nullable=True),
            sa.Column("unrealized_pnl_pct", sa.Float(), nullable=True),
            sa.Column("health_ratio", sa.Float(), nullable=True),
            sa.Column("distance_to_liquidation_pct", sa.Float(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="OPEN", index=True),
            sa.Column("exit_price", sa.Float(), nullable=True),
            sa.Column("exit_reason", sa.String(30), nullable=True),
            sa.Column("closed_at", sa.DateTime(), nullable=True, index=True),
            sa.Column("realized_pnl", sa.Float(), nullable=True),
            sa.Column("realized_pnl_pct", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    # ── gold_kill_switch_events ─────────────────────────────────
    if KILL_SWITCH not in existing:
        op.create_table(
            KILL_SWITCH,
            sa.Column("id", sa.String(50), primary_key=True),
            sa.Column("triggered_at", sa.DateTime(), nullable=False, index=True),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("rule", sa.String(50), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("metrics", sa.JSON(), nullable=True),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("resolution", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    # ── gold_portfolio_holdings ─────────────────────────────────
    if HOLDINGS not in existing:
        op.create_table(
            HOLDINGS,
            sa.Column("id", sa.String(50), primary_key=True),
            sa.Column("asset_symbol", sa.String(50), nullable=False, index=True),
            sa.Column("asset_type", sa.String(30), nullable=False),
            sa.Column("quantity", sa.Float(), nullable=False),
            sa.Column("entry_price_irr", sa.Float(), nullable=False),
            sa.Column("entry_usd_rate", sa.Float(), nullable=False),
            sa.Column("entry_date", sa.DateTime(), nullable=False, index=True),
            sa.Column("fees_pct", sa.Float(), nullable=False, server_default="0"),
            sa.Column("exit_price_irr", sa.Float(), nullable=True),
            sa.Column("exit_usd_rate", sa.Float(), nullable=True),
            sa.Column("exit_date", sa.DateTime(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="OPEN", index=True),
            sa.Column("realized_pnl_irr", sa.Float(), nullable=True),
            sa.Column("realized_dollar_roi_pct", sa.Float(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )


def downgrade() -> None:
    existing = _existing()
    if HOLDINGS in existing:
        op.drop_table(HOLDINGS)
    if KILL_SWITCH in existing:
        op.drop_table(KILL_SWITCH)
    if FUTURES in existing:
        op.drop_table(FUTURES)
