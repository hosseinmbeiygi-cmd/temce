"""0044 - Currency manual positions tracker.

Adds ``currency_manual_positions`` for the standalone currency_service
(apps/currency_service). Single table, owned by this service; uses the
shared ``models.base.Base`` so the engine already in ``core.database``
creates it via ``register_all_models()``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "currency_manual_positions",
        sa.Column("id", sa.Numeric(18, 0), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("asset_type", sa.String(16), nullable=False),
        sa.Column("entry_price", sa.Numeric(18, 0), nullable=False),
        sa.Column("volume", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "entry_date",
            sa.Date(),
            nullable=False,
            server_default=sa.text("CURRENT_DATE"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("note", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_currency_positions_user_asset",
        "currency_manual_positions",
        ["user_id", "asset_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_currency_positions_user_asset", table_name="currency_manual_positions")
    op.drop_table("currency_manual_positions")
