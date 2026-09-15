"""Add computed filter columns f77–f84 to screener_profiles.

The ORM model (``models/screener.py`` → ``ScreenerProfile``) declares the
auto-computed filter columns (ستون‌های ۷۷–۸۴) but migration 0008 never created
them, and the AI report service reads them via ``profile.get("f77_...")`` —
they were silently absent (the "فیلترهای محاسباتی فعال" section never fired).

Additive + idempotent: every column is added only if missing, with the same
``server_default="0"`` the model declares.

Revision ID: 0049
Revises: 0048
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0049"
down_revision: str | None = "0048"
branch_labels: str | None = None
depends_on: str | None = None

_FILTER_COLUMNS: list[tuple[str, str]] = [
    ("f77_dollar_eps_growth", "نرخ رشد دلاری EPS > ۱۵٪ — ستون ۷۷"),
    ("f78_real_eps_growth", "نرخ رشد واقعی EPS > ۱۵٪ — ستون ۷۸"),
    ("f79_pe_ratio_ok", "ضریب P/E < ۱.۲ — ستون ۷۹"),
    ("f80_yield_gt_bank", "بازده سهام > نرخ سود بانکی — ستون ۸۰"),
    ("f81_inst_ratio_ok", "نسبت خرید خالص حقوقی > ۵٪ شناور — ستون ۸۱"),
    ("f82_volume_spike", "جهش حجمی > ۳ برابر میانگین — ستون ۸۲"),
    ("f83_liquidity_ok", "نقدشوندگی > ۰.۵٪ شناور در روز — ستون ۸۳"),
    ("f84_loss_ratio_ok", "نسبت زیان انباشته به سرمایه < ۵۰٪ — ستون ۸۴"),
]


def upgrade() -> None:
    conn = op.get_bind()
    existing = {
        row[0]
        for row in conn.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'screener_profiles'"
            )
        )
    }
    for name, comment in _FILTER_COLUMNS:
        if name in existing:
            continue
        op.add_column(
            "screener_profiles",
            sa.Column(name, sa.Integer(), nullable=True, server_default="0", comment=comment),
        )


def downgrade() -> None:
    conn = op.get_bind()
    existing = {
        row[0]
        for row in conn.execute(
            sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'screener_profiles'"
            )
        )
    }
    for name, _comment in reversed(_FILTER_COLUMNS):
        if name not in existing:
            continue
        op.drop_column("screener_profiles", name)
