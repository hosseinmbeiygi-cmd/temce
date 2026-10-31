"""Add the MFA delivery method column to the users table.

Adds ``mfa_method`` (\"totp\" | \"email\" | \"telegram\" | NULL) so users can
choose how their one-time codes are delivered — an authenticator app
(TOTP) or a code sent to email/Telegram (via ``generate_otp``).

Revision ID: 0023_add_user_mfa_method
Revises: 0022_add_user_mfa_columns
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0023_add_user_mfa_method"
down_revision = "0022_add_user_mfa_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("mfa_method", sa.String(16), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("mfa_method")
