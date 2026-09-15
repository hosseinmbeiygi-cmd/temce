"""Add funds table — stores daily snapshots of investment fund market data.

This table powers both the /funds API and the frontend fund analysis
engine (fund-analysis.ts). Each row represents one fund's daily snapshot
with all 24 columns needed for the 6-dimension scoring system.

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-27
"""

from __future__ import annotations

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: ClassVar[set[str] | None] = None
depends_on: ClassVar[set[str] | None] = None


def upgrade() -> None:
    op.create_table(
        "funds",
        # ── Identity ──────────────────────────────────────────
        sa.Column("id", sa.String(50), primary_key=True, comment="شناسه یکتای داخلی (مثلاً fund_abc123)"),
        sa.Column("symbol", sa.String(20), nullable=False, unique=True, index=True, comment="نماد صندوق (مثلاً آگاس)"),
        sa.Column("name", sa.String(200), nullable=False, comment="نام کامل صندوق"),
        sa.Column("isin", sa.String(20), nullable=True, unique=True, comment="کد ISIN (شناسه بین‌المللی)"),
        sa.Column(
            "fund_type",
            sa.String(30),
            nullable=True,
            index=True,
            comment="نوع صندوق: سهامی / درآمد ثابت / اهرمی / مختلط / بخشی / اختصاصی",
        ),
        # ── Pricing ─────────────────────────────────────────────
        sa.Column("nav", sa.Float(), nullable=True, comment="ارزش خالص دارایی‌ها (NAV)"),
        sa.Column("nav_change", sa.Float(), nullable=True, comment="تغییر NAV نسبت به روز قبل"),
        sa.Column("nav_change_pct", sa.Float(), nullable=True, comment="درصد تغییر NAV"),
        sa.Column("price_last", sa.Float(), nullable=True, comment="آخرین قیمت معامله"),
        sa.Column("price_close", sa.Float(), nullable=True, comment="قیمت پایانی"),
        sa.Column("price_yesterday", sa.Float(), nullable=True, comment="قیمت پایانی روز قبل"),
        sa.Column("price_max", sa.Float(), nullable=True, comment="بیشترین قیمت روز"),
        sa.Column("price_min", sa.Float(), nullable=True, comment="کمترین قیمت روز"),
        # ── Trading ─────────────────────────────────────────────
        sa.Column("trade_volume", sa.BigInteger(), nullable=True, comment="حجم معاملات (تعداد)"),
        sa.Column("trade_value", sa.Float(), nullable=True, comment="ارزش معاملات (تومان)"),
        sa.Column("trade_count", sa.Integer(), nullable=True, comment="تعداد معاملات"),
        sa.Column("shares_count", sa.BigInteger(), nullable=True, comment="تعداد واحدهای صندوق"),
        sa.Column("base_volume", sa.BigInteger(), nullable=True, comment="حجم پایه"),
        sa.Column("market_value", sa.Float(), nullable=True, comment="ارزش بازار (تومان)"),
        # ── Real/Legal ──────────────────────────────────────────
        sa.Column("buy_real_volume", sa.BigInteger(), nullable=True, comment="حجم خرید حقیقی"),
        sa.Column("buy_legal_volume", sa.BigInteger(), nullable=True, comment="حجم خرید حقوقی"),
        sa.Column("sell_real_volume", sa.BigInteger(), nullable=True, comment="حجم فروش حقیقی"),
        sa.Column("sell_legal_volume", sa.BigInteger(), nullable=True, comment="حجم فروش حقوقی"),
        # ── Metadata ────────────────────────────────────────────
        sa.Column("time", sa.String(10), nullable=True, comment="زمان ثبت (HH:MM:SS)"),
        sa.Column("data_source", sa.String(30), nullable=True, comment="منبع داده (tsetmc, brsapi, fundbase)"),
        sa.Column("snapshot_date", sa.String(10), nullable=True, index=True, comment="تاریخ اسنپ‌شات (YYYY-MM-DD)"),
        sa.Column("extra", sa.Text(), nullable=True, comment="داده‌های اضافی (JSON)"),
        # ── Timing (inherited from TimestampMixin) ─────────────
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # Performance indexes for common query patterns
    op.create_index("ix_funds_type_nav", "funds", ["fund_type", "nav"])
    op.create_index("ix_funds_symbol_type", "funds", ["symbol", "fund_type"])


def downgrade() -> None:
    op.drop_index("ix_funds_symbol_type", "funds")
    op.drop_index("ix_funds_type_nav", "funds")
    op.drop_table("funds")
