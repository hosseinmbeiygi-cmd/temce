"""GoldDesk ownership: per-user holdings, trades, DCA, alerts, portfolio values.

Revision ID: 0120
Revises: 0119
Create Date: 2026-10-30

Before this migration every authenticated account shared one gold portfolio,
one trade ledger, one DCA plan set, one alert rule set and one daily portfolio
value row. ``user_id`` is nullable; legacy rows stay NULL and are visible to
admins only (the same policy as migration 0117 for alerts/watchlist).

The daily portfolio-value key changes from ``UNIQUE (as_of)`` to
``UNIQUE (user_id, as_of)`` so two users can have a row for the same day.
"""

from __future__ import annotations

from alembic import op

revision = "0120"
down_revision = "0119_service_private_tables"
branch_labels = None
depends_on = None

_TABLES = (
    "gold_holdings",
    "gold_dca_plans",
    "gold_trades",
    "gold_alert_rules",
    "gold_alert_events",
)


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS user_id VARCHAR(100)")
        op.execute(f"CREATE INDEX IF NOT EXISTS ix_{table}_user_id ON {table} (user_id)")

    op.execute(
        "ALTER TABLE gold_portfolio_values ADD COLUMN IF NOT EXISTS user_id VARCHAR(100)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_gold_portfolio_values_user_id "
        "ON gold_portfolio_values (user_id)"
    )
    # Drop the legacy global UNIQUE(as_of). It may exist as a standalone unique
    # index (created by an older model) rather than a table constraint.
    op.execute("DROP INDEX IF EXISTS uq_gold_portfolio_values_as_of")
    op.execute(
        """
        DO $$
        DECLARE con record;
        BEGIN
            FOR con IN
                SELECT c.conname
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                WHERE t.relname = 'gold_portfolio_values'
                  AND c.contype = 'u'
                  AND c.conkey = ARRAY[
                        (SELECT a.attnum
                         FROM pg_attribute a
                         WHERE a.attrelid = t.oid
                           AND a.attname = 'as_of'
                           AND NOT a.attisdropped)
                      ]
            LOOP
                EXECUTE format('ALTER TABLE gold_portfolio_values DROP CONSTRAINT %I', con.conname);
            END LOOP;
        END $$;
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_gold_portfolio_user_day "
        "ON gold_portfolio_values (user_id, as_of)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_gold_portfolio_user_day")
    op.execute("DROP INDEX IF EXISTS ix_gold_portfolio_values_user_id")
    op.execute("ALTER TABLE gold_portfolio_values DROP COLUMN IF EXISTS user_id")
    for table in _TABLES:
        op.execute(f"DROP INDEX IF EXISTS ix_{table}_user_id")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS user_id")
    # The legacy UNIQUE(as_of) is not restored: it fails as soon as two users
    # have a row for the same day, which the upgrade explicitly allowed.
