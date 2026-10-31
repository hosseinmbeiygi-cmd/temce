"""0043 – GoldDesk: حذف نرم دارایی (deleted_at) + FK معامله به SET NULL.

Revision ID: 0043_gold_holding_soft_delete
Revises: 0115
Create Date: 2026-10-24

تغییرات:
  * ستون ``deleted_at`` روی جدول ``gold_holdings`` — داراییٔ software-deleted
    با این ستون علامت‌گذاری می‌شود و ردیف físico پاک نمی‌شود.
  * FK ``gold_trades.holding_id`` از ``ondelete="CASCADE"`` به
    ``ondelete="SET NULL"`` تغییر می‌کند تا حذف (حتی نرم/سخت) دارایی،
    Conances معاملهٔ آن را از بین ن‌برد ( گزارش مالیاتی و موجودی معامله سالم بماند).
  * ایندکس روی FKهای ``holding_id``، ``plan_id`` (جدول ``gold_trades``) و
    ``rule_id`` (جدول ``gold_alert_events``) برای کوئریهای JOIN/فیلتر.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0043_gold_holding_soft_delete"
down_revision = "0115"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── gold_holdings: ستون deleted_at ──
    op.add_column(
        "gold_holdings",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_holdings_deleted_at", "gold_holdings", ["deleted_at"])

    # ── gold_trades.holding_id: CASCADE ⇒ SET NULL ──
    op.drop_constraint(
        "gold_trades_holding_id_fkey", "gold_trades", type_="foreignkey"
    )
    op.create_foreign_key(
        "gold_trades_holding_id_fkey",
        "gold_trades",
        "gold_holdings",
        ["holding_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ── ایندکس FKها (بخش داده) ──
    op.create_index("ix_gold_trades_holding_id", "gold_trades", ["holding_id"])
    op.create_index("ix_gold_trades_plan_id", "gold_trades", ["plan_id"])
    op.create_index("ix_gold_alert_events_rule_id", "gold_alert_events", ["rule_id"])


def downgrade() -> None:
    op.drop_index("ix_gold_alert_events_rule_id", table_name="gold_alert_events")
    op.drop_index("ix_gold_trades_plan_id", table_name="gold_trades")
    op.drop_index("ix_gold_trades_holding_id", table_name="gold_trades")
    op.drop_constraint(
        "gold_trades_holding_id_fkey", "gold_trades", type_="foreignkey"
    )
    op.create_foreign_key(
        "gold_trades_holding_id_fkey",
        "gold_trades",
        "gold_holdings",
        ["holding_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_index("ix_holdings_deleted_at", table_name="gold_holdings")
    op.drop_column("gold_holdings", "deleted_at")
