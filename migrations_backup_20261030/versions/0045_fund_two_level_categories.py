"""Two-level fund categories + sub_type + scoring config history.

Revision ID: 0045
Revises: 0044
Create Date: 2026-09-01
"""

from __future__ import annotations

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "0045"
down_revision: str | None = "0044"
branch_labels: ClassVar[set[str] | None] = None
depends_on: ClassVar[set[str] | None] = None


# ── Canonical taxonomy (group + 8 sector sub-groups) ───────────────────────
CATEGORIES: list[dict[str, str | None]] = [
    # Root groups
    {"code": "fixed_income", "label": "درآمد ثابت", "parent": None},
    {"code": "equity", "label": "سهامی", "parent": None},
    {"code": "mixed", "label": "مختلط", "parent": None},
    {"code": "index", "label": "شاخصی", "parent": None},
    {"code": "fof", "label": "صندوق در صندوق", "parent": None},
    {"code": "private", "label": "تامین مالی خصوصی", "parent": None},
    {"code": "guaranteed", "label": "تضمین اصل سرمایه", "parent": None},
    {"code": "leveraged", "label": "اهرمی", "parent": None},
    {"code": "gold", "label": "طلا و فلزات گران‌بها", "parent": None},
    {"code": "silver", "label": "نقره", "parent": None},
    {"code": "commodity", "label": "کالایی", "parent": None},
    {"code": "sector", "label": "بخشی", "parent": None},
    {"code": "real_estate", "label": "زمین و ساختمان / REIT", "parent": None},
    {"code": "vc", "label": "جسورانه VC", "parent": None},
    {"code": "other", "label": "سایر", "parent": None},
    # Sector sub-groups (children of sector) — the key addition
    {"code": "sector_refinery", "label": "پالایشی", "parent": "sector"},
    {"code": "sector_petrochemical", "label": "پتروشیمی", "parent": "sector"},
    {"code": "sector_auto", "label": "خودرو و قطعه", "parent": "sector"},
    {"code": "sector_metals", "label": "فلزات / فولاد-معدنی", "parent": "sector"},
    {"code": "sector_pharma", "label": "دارویی", "parent": "sector"},
    {"code": "sector_bank", "label": "بانکی و اعتباری", "parent": "sector"},
    {"code": "sector_cement", "label": "سیمانی", "parent": "sector"},
    {"code": "sector_tech", "label": "فناوری اطلاعات", "parent": "sector"},
]


def upgrade() -> None:
    # 1) fund_categories table
    op.create_table(
        "fund_categories",
        sa.Column("code", sa.String(40), primary_key=True, comment="کد یکتا دسته"),
        sa.Column("label", sa.String(80), nullable=False, comment="نام فارسی"),
        sa.Column(
            "parent_code",
            sa.String(40),
            sa.ForeignKey("fund_categories.code"),
            nullable=True,
            comment="دسته والد (null=گروه اصلی)",
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_fund_categories_parent", "fund_categories", ["parent_code"])

    # Seed categories
    fund_categories = sa.table(
        "fund_categories",
        sa.column("code", sa.String),
        sa.column("label", sa.String),
        sa.column("parent_code", sa.String),
        sa.column("sort_order", sa.Integer),
    )
    for i, cat in enumerate(CATEGORIES):
        op.execute(
            fund_categories.insert().values(
                code=cat["code"], label=cat["label"], parent_code=cat["parent"], sort_order=i
            )
        )

    # 2) Add sub_type to funds (nullable, FK to fund_categories)
    op.add_column(
        "funds",
        sa.Column(
            "sub_type",
            sa.String(40),
            sa.ForeignKey("fund_categories.code"),
            nullable=True,
            comment="زیرگروه بخشی (null=بدون زیرگروه)",
        ),
    )
    op.create_index("ix_funds_sub_type", "funds", ["sub_type"])
    op.create_index("ix_funds_type_subtype", "funds", ["fund_type", "sub_type"])

    # 3) scoring_config_history (config versioning)
    op.create_table(
        "scoring_config_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("version", sa.Integer(), nullable=False, comment="نسخه پیکربندی"),
        sa.Column("group_code", sa.String(40), sa.ForeignKey("fund_categories.code"), nullable=False),
        sa.Column("weights", sa.JSON(), nullable=False, comment="وزن 56 شاخص به صورت JSON"),
        sa.Column("created_by", sa.String(80), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_scoring_config_group_version", "scoring_config_history", ["group_code", "version"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_scoring_config_group_version", table_name="scoring_config_history")
    op.drop_table("scoring_config_history")
    op.drop_index("ix_funds_type_subtype", table_name="funds")
    op.drop_index("ix_funds_sub_type", table_name="funds")
    op.drop_column("funds", "sub_type")
    op.drop_index("ix_fund_categories_parent", table_name="fund_categories")
    op.drop_table("fund_categories")
