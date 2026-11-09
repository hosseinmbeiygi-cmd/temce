"""GoldDesk ownership enforcement: backfill NULL user_id and add NOT NULL.

Revision ID: 0122
Revises: 0121
Create Date: 2026-11-09

Migration 0120 added ``user_id`` as nullable.  Legacy rows that pre-date that
migration have ``user_id = NULL``; they are visible to admins but invisible to
regular users.  This migration:

1. Backfills every ``NULL`` user_id to the first admin user found in the
   ``users`` table (roles LIKE '%admin%', ordered by created_at).  If no admin
   user exists (e.g. a freshly created test database), the placeholder string
   ``'__legacy_admin__'`` is used so the subsequent NOT NULL constraint can
   still be applied.

2. Adds ``NOT NULL`` to ``user_id`` on all six personal-data tables, making
   the schema-layer guarantee that every personal row has an explicit owner.

Decision D1 (approved 2026-11-09): backfill target = admin user.
Decision D2 is in portfolio.py (code change, not a migration).
"""

from __future__ import annotations

from alembic import op

revision = "0122"
down_revision = "0121"
branch_labels = None
depends_on = None

_PERSONAL_TABLES = (
    "gold_holdings",
    "gold_dca_plans",
    "gold_trades",
    "gold_alert_rules",
    "gold_alert_events",
    "gold_portfolio_values",
)

_BACKFILL_SQL = """
UPDATE {table}
SET user_id = COALESCE(
    (SELECT id FROM users
     WHERE roles LIKE '%admin%'
     ORDER BY created_at
     LIMIT 1),
    '__legacy_admin__'
)
WHERE user_id IS NULL
"""


def upgrade() -> None:
    for table in _PERSONAL_TABLES:
        op.execute(_BACKFILL_SQL.format(table=table))

    for table in _PERSONAL_TABLES:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN user_id SET NOT NULL"
        )


def downgrade() -> None:
    for table in _PERSONAL_TABLES:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN user_id DROP NOT NULL"
        )
    # Data is not reverted: backfilled rows keep their user_id.
