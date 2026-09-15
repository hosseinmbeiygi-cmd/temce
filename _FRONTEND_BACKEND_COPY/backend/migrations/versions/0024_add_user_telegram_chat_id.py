"""Add per-user Telegram chat ID to the users table.

Stores the Telegram chat ID on each user so MFA codes can be delivered to
the correct chat in multi-user setups. When unset, the global
``settings.telegram_chat_id`` is used as a fallback.

Revision ID: 0024_add_user_telegram_chat_id
Revises: 0023_add_user_mfa_method
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0024_add_user_telegram_chat_id"
down_revision = "0023_add_user_mfa_method"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("telegram_chat_id", sa.String(64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("telegram_chat_id")
