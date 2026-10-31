"""0041 – GoldDesk tables (5 tables).

Revision ID: 0041
Revises: 0040
Create Date: 2026-08-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── gold_snapshots ────────────────────────────────────────────
    op.create_table(
        "gold_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(64), nullable=False),
        sa.Column("asset_type", sa.String(16), nullable=False),
        sa.Column("market_price", sa.Float(), nullable=False),
        sa.Column("fair_value", sa.Float(), nullable=True),
        sa.Column("bubble_abs", sa.Float(), nullable=True),
        sa.Column("bubble_pct", sa.Float(), nullable=True),
        sa.Column("implied_usd", sa.Float(), nullable=True),
        sa.Column("xau_usd", sa.Float(), nullable=True),
        sa.Column("usd_irt", sa.Float(), nullable=True),
        sa.Column("aed_irt", sa.Float(), nullable=True),
        sa.Column("aed_parity_usd", sa.Float(), nullable=True),
        sa.Column("aed_gap_pct", sa.Float(), nullable=True),
        sa.Column("quality_flag", sa.String(16), server_default="clean"),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_snap_symbol_time", "gold_snapshots", ["symbol", "snapshot_at"])
    op.create_index("ix_snap_snapshot_at", "gold_snapshots", ["snapshot_at"])

    # ── gold_fund_nav ─────────────────────────────────────────────
    op.create_table(
        "gold_fund_nav",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("fund_name", sa.String(64), nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("nav_per_unit", sa.Float(), nullable=False),
        sa.Column("market_price", sa.Float(), nullable=False),
        sa.Column("bubble_abs", sa.Float(), server_default="0"),
        sa.Column("bubble_pct", sa.Float(), server_default="0"),
        sa.Column("units_traded", sa.BigInteger(), server_default="0"),
        sa.Column("real_buy_value", sa.BigInteger(), server_default="0"),
        sa.Column("real_sell_value", sa.BigInteger(), server_default="0"),
        sa.Column("bpr", sa.Float(), server_default="0"),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_fundnav_symbol", "gold_fund_nav", ["symbol"])
    op.create_unique_constraint("uq_fundnav_symbol_date", "gold_fund_nav", ["symbol", "date"])

    # ── gold_alert_rules ──────────────────────────────────────────
    op.create_table(
        "gold_alert_rules",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("rule_type", sa.String(32), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("channel", sa.String(16), server_default="inapp"),
        sa.Column("telegram_chat_id", sa.String(32), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("cooldown_minutes", sa.Integer(), server_default="30"),
        sa.Column("last_fired_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_alert_symbol", "gold_alert_rules", ["symbol"])

    # ── gold_alert_events ─────────────────────────────────────────
    op.create_table(
        "gold_alert_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "rule_id",
            sa.BigInteger(),
            sa.ForeignKey("gold_alert_rules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rule_name", sa.String(64), nullable=True),
        sa.Column("symbol", sa.String(32), nullable=True),
        sa.Column("trigger_value", sa.Float(), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("channel", sa.String(16), server_default="inapp"),
        sa.Column("sent_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("read_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_event_sent_at", "gold_alert_events", ["sent_at"])
    op.create_index("ix_event_read_at", "gold_alert_events", ["read_at"])

    # ── gold_score_history ───────────────────────────────────────
    op.create_table(
        "gold_score_history",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("total_score", sa.Float(), nullable=False),
        sa.Column("components_json", sa.Text(), nullable=False),
        sa.Column("decision", sa.String(16), nullable=True),
        sa.Column("hard_stop_active", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("hard_stop_reason", sa.String(256), nullable=True),
        sa.Column("score_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_score_at", "gold_score_history", ["score_at"])


def downgrade() -> None:
    op.drop_index("ix_score_at", table_name="gold_score_history")
    op.drop_table("gold_score_history")
    op.drop_index("ix_event_read_at", table_name="gold_alert_events")
    op.drop_index("ix_event_sent_at", table_name="gold_alert_events")
    op.drop_table("gold_alert_events")
    op.drop_index("ix_alert_symbol", table_name="gold_alert_rules")
    op.drop_table("gold_alert_rules")
    op.drop_constraint("uq_fundnav_symbol_date", "gold_fund_nav", type_="unique")
    op.drop_index("ix_fundnav_symbol", table_name="gold_fund_nav")
    op.drop_table("gold_fund_nav")
    op.drop_index("ix_snap_snapshot_at", table_name="gold_snapshots")
    op.drop_index("ix_snap_symbol_time", table_name="gold_snapshots")
    op.drop_table("gold_snapshots")
