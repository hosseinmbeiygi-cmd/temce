"""Bale messenger (bale.ai) as a second notification channel.

Mirrors the Telegram surface:
* ``users.bale_chat_id`` — the per-user chat linked to their account (the
  engine notifier delivers only to the chat linked to the alert's own owner).
* ``alert_notifications.bale_state/bale_attempts/bale_error/bale_at`` — honest
  per-channel delivery state alongside the telegram_* columns.

Revision ID: 0130
Revises: 0129
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0130"
down_revision = "0129"
branch_labels = None
depends_on = None


def _columns(conn: sa.Connection, table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns(table)}


def upgrade() -> None:
    conn = op.get_bind()

    if "bale_chat_id" not in _columns(conn, "users"):
        op.add_column("users", sa.Column("bale_chat_id", sa.String(64), nullable=True))

    cols = _columns(conn, "alert_notifications")
    if "bale_state" not in cols:
        op.add_column(
            "alert_notifications",
            sa.Column("bale_state", sa.String(20), nullable=False, server_default="not_requested"),
        )
    if "bale_attempts" not in cols:
        op.add_column(
            "alert_notifications",
            sa.Column("bale_attempts", sa.Integer, nullable=False, server_default="0"),
        )
    if "bale_error" not in cols:
        op.add_column("alert_notifications", sa.Column("bale_error", sa.Text))
    if "bale_at" not in cols:
        op.add_column("alert_notifications", sa.Column("bale_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    conn = op.get_bind()
    cols = _columns(conn, "alert_notifications")
    for name in ("bale_at", "bale_error", "bale_attempts", "bale_state"):
        if name in cols:
            op.drop_column("alert_notifications", name)
    if "bale_chat_id" in _columns(conn, "users"):
        op.drop_column("users", "bale_chat_id")
