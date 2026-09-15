"""Add queue_analysis_results table — stores 5 queue features + adjusted scores + decision per symbol.

This table is the Sink layer for QueueAnalysisService. Every call to
analyze_symbol() and analyze_market() can optionally persist the result
here, enabling:
  - Historical comparison of queue status across days
  - Audit of queue-driven decisions
  - Trend analysis (e.g. "which symbols had 3+ consecutive buy queues")
  - Integration with the Feature Engine (Block F: Microstructure & Queue)

Columns follow the same structure as QueueAnalysisResult model.

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-27
"""

from __future__ import annotations

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: ClassVar[set[str] | None] = None
depends_on: ClassVar[set[str] | None] = None


def upgrade() -> None:
    op.create_table(
        "queue_analysis_results",
        # ── Identity ──────────────────────────────────────────
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(20), nullable=False, index=True, comment="نماد بورسی (مثلاً فولاد)"),
        sa.Column(
            "run_id", sa.String(50), nullable=False, index=True, comment="شناسه اجرا (مثلاً auto-20260727-153000)"
        ),
        sa.Column(
            "market_type",
            sa.String(20),
            nullable=False,
            server_default="bours",
            comment="نوع بازار: bours / farabours / base_market",
        ),
        # ── 5 Queue Features ──────────────────────────────────
        sa.Column(
            "queue_status", sa.String(20), nullable=False, index=True, comment="وضعیت صف: BUY_QUEUE / SELL_QUEUE / NONE"
        ),
        sa.Column(
            "queue_volume_ratio",
            sa.Float(),
            nullable=False,
            server_default="0",
            comment="نسبت حجم صف به کل سفارشات (0-1)",
        ),
        sa.Column(
            "queue_days_streak",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="تعداد روزهای متوالی در صف (امروز + تاریخچه)",
        ),
        sa.Column(
            "queue_type_change",
            sa.String(20),
            nullable=False,
            server_default="NO_CHANGE",
            comment="نوع تغییر صف: NEW_BUY_QUEUE / NEW_SELL_QUEUE / QUEUE_BROKEN / NO_CHANGE",
        ),
        sa.Column(
            "distance_to_limit", sa.Float(), nullable=False, server_default="0", comment="فاصله تا سقف/کف دامنه (درصد)"
        ),
        # ── Metadata ───────────────────────────────────────────
        sa.Column("last_price", sa.Float(), nullable=True, comment="آخرین قیمت معامله‌شده"),
        sa.Column("limit_up", sa.Float(), nullable=True, comment="سقف مجاز روزانه (tmax)"),
        sa.Column("limit_down", sa.Float(), nullable=True, comment="کف مجاز روزانه (tmin)"),
        sa.Column("queue_buy_volume", sa.BigInteger(), nullable=True, comment="حجم سفارشات خرید باقی‌مانده در صف"),
        sa.Column("queue_sell_volume", sa.BigInteger(), nullable=True, comment="حجم سفارشات فروش باقی‌مانده در صف"),
        # ── Adjusted Scores ─────────────────────────────────────
        sa.Column("adjusted_liquidity", sa.Float(), nullable=True, comment="S_L تعدیل‌شده (نقدشوندگی)"),
        sa.Column("adjusted_technical", sa.Float(), nullable=True, comment="S_T تعدیل‌شده (تکنیکال)"),
        sa.Column("adjusted_orderflow", sa.Float(), nullable=True, comment="S_O تعدیل‌شده (جریان پول)"),
        sa.Column("adjusted_penalty", sa.Float(), nullable=True, comment="Penalty تعدیل‌شده (جریمه)"),
        sa.Column("liquidity_delta", sa.Float(), nullable=True, comment="تغییر S_L نسبت به پایه"),
        sa.Column("technical_delta", sa.Float(), nullable=True, comment="تغییر S_T نسبت به پایه"),
        sa.Column("orderflow_delta", sa.Float(), nullable=True, comment="تغییر S_O نسبت به پایه"),
        sa.Column("penalty_delta", sa.Float(), nullable=True, comment="تغییر Penalty نسبت به پایه"),
        # ── Decision ──────────────────────────────────────────
        sa.Column(
            "final_decision",
            sa.String(20),
            nullable=True,
            comment="تصمیم نهایی: BUY / WATCHLIST / HOLD / REDUCE / REJECT / NEUTRAL",
        ),
        sa.Column(
            "overridden",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="آیا Hard Rule فعال شده است؟",
        ),
        sa.Column("override_reason", sa.Text(), nullable=True, comment="دلیل override در صورت فعال بودن"),
        # ── Interpretation ─────────────────────────────────────
        sa.Column(
            "interpretation",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
            comment="تفسیر انسانی وضعیت صف (status_fa, volume_fa, ...)",
        ),
        # ── Timing ────────────────────────────────────────────
        sa.Column(
            "analyzed_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), comment="زمان انجام تحلیل"
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Performance indexes for common query patterns
    op.create_index(
        "ix_queue_symbol_status",
        "queue_analysis_results",
        ["symbol", "queue_status"],
    )
    op.create_index(
        "ix_queue_status_analyzed",
        "queue_analysis_results",
        ["queue_status", "analyzed_at"],
    )
    op.create_index(
        "ix_queue_run_id",
        "queue_analysis_results",
        ["run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_queue_run_id", "queue_analysis_results")
    op.drop_index("ix_queue_status_analyzed", "queue_analysis_results")
    op.drop_index("ix_queue_symbol_status", "queue_analysis_results")
    op.drop_table("queue_analysis_results")
