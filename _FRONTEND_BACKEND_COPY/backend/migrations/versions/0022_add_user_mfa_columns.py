"""Add MFA/TOTP columns to the users table.

Adds ``totp_secret`` (base32), ``totp_enabled`` and ``totp_confirmed_at``
so users can enroll in time-based one-time-password two-factor auth.

Revision ID: 0022_add_user_mfa_columns
Revises: 0021_news_published_at_width
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0022_add_user_mfa_columns"
down_revision = "0021_news_published_at_width"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("totp_secret", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")))
        batch_op.add_column(sa.Column("totp_confirmed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("totp_confirmed_at")
        batch_op.drop_column("totp_enabled")
        batch_op.drop_column("totp_secret")
