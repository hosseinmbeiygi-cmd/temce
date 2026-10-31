"""Widen news_articles.published_at from VARCHAR(30) to VARCHAR(40)

RSS/Atom dates serialized via ``datetime.isoformat()`` with microseconds
(e.g. ``2026-08-03T06:00:51.123456+00:00``) are 36 chars — wider than the
original VARCHAR(30), causing ``StringDataRightTruncationError`` on insert
(the title/summary/content/url columns were already TEXT/VARCHAR(500);
``published_at`` was the remaining 30-char bottleneck).

The repository also normalizes datetimes to second precision (max 25 chars),
so this widening is defense-in-depth for any other writer.

Revision ID: 0021_news_published_at_width
Revises: 0020_brsapi_snapshots_unique
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0021_news_published_at_width"
down_revision = "0020_brsapi_snapshots_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("news_articles") as batch_op:
        batch_op.alter_column(
            "published_at",
            existing_type=sa.String(30),
            type_=sa.String(40),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("news_articles") as batch_op:
        batch_op.alter_column(
            "published_at",
            existing_type=sa.String(40),
            type_=sa.String(30),
            existing_nullable=True,
        )
