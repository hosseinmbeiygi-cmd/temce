"""
Add 8 price/volume/trading columns to screener_profiles.

Columns added:
  - current_price       (Float)    — قیمت روز سهم — ستون ۲۶
  - price_change_pct    (Float)    — تغییر قیمت امروز (درصد) — ستون ۴۱
  - today_volume        (BigInt)   — حجم معاملات امروز — ستون ۳۶
  - avg_daily_value     (Float)    — میانگین ارزش معاملات روزانه — ستون ۳۹
  - institutional_buy   (BigInt)   — خرید حقوقی ۳۰ روز — ستون ۴۷
  - institutional_sell  (BigInt)   — فروش حقوقی ۳۰ روز — ستون ۴۸
  - farabourse_volume   (BigInt)   — حجم معاملات فرابورس — ستون ۴۳
  - farabourse_price    (Float)    — قیمت سهم در فرابورس — ستون ۴۵

Revision ID: 0011
Revises: 0010
"""

from __future__ import annotations

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: ClassVar[set[str] | None] = None
depends_on: ClassVar[set[str] | None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Add columns one by one (IF NOT EXISTS check for idempotency)
    columns = [
        ("current_price", "DOUBLE PRECISION", "قیمت روز سهم — ستون ۲۶"),
        ("price_change_pct", "DOUBLE PRECISION", "تغییر قیمت امروز (درصد) — ستون ۴۱"),
        ("today_volume", "BIGINT", "حجم معاملات امروز — ستون ۳۶"),
        ("avg_daily_value", "DOUBLE PRECISION", "میانگین ارزش معاملات روزانه (تومان) — ستون ۳۹"),
        ("institutional_buy", "BIGINT", "خرید حقوقی ۳۰ روز — ستون ۴۷"),
        ("institutional_sell", "BIGINT", "فروش حقوقی ۳۰ روز — ستون ۴۸"),
        ("farabourse_volume", "BIGINT", "حجم معاملات فرابورس (هفته) — ستون ۴۳"),
        ("farabourse_price", "DOUBLE PRECISION", "قیمت سهم در فرابورس — ستون ۴۵"),
    ]

    for col_name, col_type, comment in columns:
        # Check if column already exists
        result = conn.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'screener_profiles' AND column_name = :col"
            ),
            {"col": col_name},
        )
        if result.fetchone():
            print(f"  Column {col_name} already exists — skipping")
            continue

        op.add_column(
            "screener_profiles",
            sa.Column(col_name, sa.Text() if "BIGINT" in col_type else sa.Float(), comment=comment),
        )
        print(f"  Added column {col_name} ({col_type})")

        # Cast the type using raw SQL
        if "BIGINT" in col_type:
            conn.execute(
                sa.text(
                    f"ALTER TABLE screener_profiles ALTER COLUMN {col_name} TYPE BIGINT USING NULLIF({col_name}, '')::BIGINT"
                )
            )
        elif "DOUBLE" in col_type:
            conn.execute(
                sa.text(
                    f"ALTER TABLE screener_profiles ALTER COLUMN {col_name} TYPE DOUBLE PRECISION USING NULLIF({col_name}, '')::DOUBLE PRECISION"
                )
            )

    print("  ✅ Migration 0011 complete")


def downgrade() -> None:
    cols = [
        "current_price",
        "price_change_pct",
        "today_volume",
        "avg_daily_value",
        "institutional_buy",
        "institutional_sell",
        "farabourse_volume",
        "farabourse_price",
    ]
    for col in cols:
        op.drop_column("screener_profiles", col)
    print("  ✅ Downgrade 0011 complete")
