"""Add avg_50d_volume column to screener_profiles.

Column added:
  - avg_50d_volume  (BigInt)  — میانگین حجم ۵۰ روزه — ستون ۳۷

This column powers the volume-spike filter (f82, ستون ۸۲) with a real
50-day average volume instead of the previous estimate derived from
avg_daily_value / current_price.

Revision ID: 0031_add_avg_50d_volume
Revises: 0030_symbol_snapshot_dashboard_index
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0031_add_avg_50d_volume"
down_revision = "0030_symbol_snapshot_dashboard_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Idempotency check: skip if column already exists
    result = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'screener_profiles' AND column_name = 'avg_50d_volume'"
        )
    )
    if result.fetchone():
        print("  Column avg_50d_volume already exists — skipping")
        return

    op.add_column(
        "screener_profiles",
        sa.Column("avg_50d_volume", sa.BigInteger(), comment="میانگین حجم ۵۰ روزه — ستون ۳۷"),
    )
    print("  Added column avg_50d_volume (BIGINT)")

    # Cast safety for any pre-existing TEXT leftovers (idempotent)
    conn.execute(
        sa.text(
            "ALTER TABLE screener_profiles ALTER COLUMN avg_50d_volume "
            "TYPE BIGINT USING NULLIF(avg_50d_volume::TEXT, '')::BIGINT"
        )
    )
    print("  ✅ Migration 0031 complete")


def downgrade() -> None:
    op.drop_column("screener_profiles", "avg_50d_volume")
    print("  ✅ Downgrade 0031 complete")
