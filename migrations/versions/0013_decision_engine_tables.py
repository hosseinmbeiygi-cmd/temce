"""Add decision engine tables for the Enterprise Decision Support System.

Two new tables:
  1. decision_architectures  — Architecture blueprint data (12-layer, 110 features, 22 services, etc.)
  2. decision_results        — Actual decision outputs per symbol (BUY/WATCHLIST/HOLD/REDUCE/REJECT/NEUTRAL)

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-27
"""

from __future__ import annotations

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: ClassVar[set[str] | None] = None
depends_on: ClassVar[set[str] | None] = None


def upgrade() -> None:
    # ════════════════════════════════════════════════════════════
    # TABLE 1: decision_architectures
    # Stores versioned architecture blueprint snapshots as JSONB
    # ════════════════════════════════════════════════════════════
    op.create_table(
        "decision_architectures",

        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("version", sa.String(50), nullable=False, unique=True, index=True,
                  comment="نسخه معماری (مثلاً Enterprise-Final-1.0)"),
        sa.Column("title", sa.String(200), nullable=False,
                  comment="عنوان نسخه معماری"),
        sa.Column("data", sa.dialects.postgresql.JSONB(), nullable=False,
                  comment="داده کامل معماری به صورت JSON (12 لایه، 110 ویژگی، 22 سرویس، 30+ جدول، 31 API)"),

        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"),
                  comment="آیا این نسخه فعال است؟"),

        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True,
                  comment="آخرین به‌روزرسانی"),
    )

    # ════════════════════════════════════════════════════════════
    # TABLE 2: decision_results
    # Stores the actual decision output for each symbol after running
    # the 3-stage pipeline (BaseScore → MicroAdjustment → Penalty → FinalDecision)
    # ════════════════════════════════════════════════════════════
    op.create_table(
        "decision_results",

        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),

        # شناسه
        sa.Column("symbol", sa.String(20), nullable=False, index=True,
                  comment="نماد بورسی"),
        sa.Column("run_id", sa.String(50), nullable=False, index=True,
                  comment="شناسه اجرا"),
        sa.Column("model_version", sa.String(50), nullable=False,
                  comment="نسخه مدل"),
        sa.Column("rulebook_version", sa.String(50), nullable=False,
                  comment="نسخه Rulebook"),

        # 8 سوبرسکور (0-100)
        sa.Column("score_fundamental", sa.Float(), nullable=True,
                  comment="S_F: امتیاز بنیادی (0-100)"),
        sa.Column("score_valuation", sa.Float(), nullable=True,
                  comment="S_V: امتیاز ارزش‌گذاری (0-100)"),
        sa.Column("score_technical", sa.Float(), nullable=True,
                  comment="S_T: امتیاز تکنیکال (0-100)"),
        sa.Column("score_liquidity", sa.Float(), nullable=True,
                  comment="S_L: امتیاز نقدشوندگی (0-100)"),
        sa.Column("score_orderflow", sa.Float(), nullable=True,
                  comment="S_O: امتیاز جریان پول (0-100)"),
        sa.Column("score_micro", sa.Float(), nullable=True,
                  comment="S_M: امتیاز ریزساختار (0-100)"),
        sa.Column("score_macro", sa.Float(), nullable=True,
                  comment="S_K: امتیاز کلان (0-100)"),
        sa.Column("score_event", sa.Float(), nullable=True,
                  comment="S_E: امتیاز رویدادی (0-100)"),

        # امتیازات میانی
        sa.Column("base_score", sa.Float(), nullable=True,
                  comment="BaseScore: مجموع وزنی 8 سوبرسکور"),
        sa.Column("micro_adjustment", sa.Float(), nullable=True,
                  comment="MicroAdjustment: اصلاح ناشی از ریزمعاملات"),
        sa.Column("penalty", sa.Float(), nullable=True,
                  comment="Penalty: ضریب جریمه ریسک (0-0.35)"),

        # نهایی
        sa.Column("final_score", sa.Float(), nullable=True,
                  comment="FinalScore: امتیاز نهایی (0-100)"),
        sa.Column("decision", sa.String(20), nullable=False,
                  comment="تصمیم نهایی: BUY / WATCHLIST / HOLD / REDUCE / REJECT / NEUTRAL"),
        sa.Column("confidence", sa.Float(), nullable=True,
                  comment="اطمینان تصمیم (0-1)"),
        sa.Column("neg_events_count", sa.Integer(), nullable=True,
                  comment="تعداد رویدادهای منفی فعال"),

        # متادیتا
        sa.Column("details", sa.dialects.postgresql.JSONB(), nullable=True,
                  comment="جزئیات کامل (دلایل، reason_codes، report)"),
        sa.Column("evaluated_at", sa.DateTime(), server_default=sa.func.now(),
                  comment="زمان ارزیابی"),
    )

    # Indexes for decision_results (query performance)
    op.create_index(
        "ix_decision_results_symbol_decision",
        "decision_results",
        ["symbol", "decision"],
    )
    op.create_index(
        "ix_decision_results_decision_final_score",
        "decision_results",
        ["decision", "final_score"],
    )
    op.create_index(
        "ix_decision_results_evaluated_at",
        "decision_results",
        ["evaluated_at"],
    )


def downgrade() -> None:
    # Drop indexes first
    op.drop_index("ix_decision_results_symbol_decision", "decision_results")
    op.drop_index("ix_decision_results_decision_final_score", "decision_results")
    op.drop_index("ix_decision_results_evaluated_at", "decision_results")

    # Drop tables
    op.drop_table("decision_results")
    op.drop_table("decision_architectures")
