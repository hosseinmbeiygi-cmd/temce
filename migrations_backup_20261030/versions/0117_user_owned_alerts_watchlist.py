"""Ownership for alerts and watchlist.

Revision ID: 0117
Revises: 0116
Create Date: 2026-10-29

``alerts`` and ``watchlist`` were global: every account shared one list and one
alert feed, and any account could read or delete another's rows (audit
SEC-04/SEC-05). This migration adds ``user_id`` to both and replaces the
watchlist's global ``UNIQUE (symbol)`` with ``UNIQUE (user_id, symbol)``.

Backfill policy: existing rows keep ``user_id = NULL`` and stay visible to
admins only. Deciding which account owns pre-ownership data is an operational
call, not something a migration should guess.

``watchlist`` may be absent (older deployments created it lazily in the
service), so the table is created first and every step is guarded.
"""

from __future__ import annotations

from alembic import op

revision = "0117"
down_revision = "0116"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS user_id VARCHAR(100)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_alerts_user_id ON alerts (user_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS watchlist (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(50) NOT NULL,
            name VARCHAR(200) DEFAULT '',
            note TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            user_id VARCHAR(100),
            created_at TIMESTAMP DEFAULT NOW()
        )
        """
    )
    op.execute("ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS user_id VARCHAR(100)")

    # Drop the legacy global UNIQUE(symbol) so two users may watch one symbol.
    op.execute(
        """
        DO $$
        DECLARE con record;
        BEGIN
            FOR con IN
                SELECT c.conname
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                WHERE t.relname = 'watchlist'
                  AND c.contype = 'u'
                  AND c.conkey = ARRAY[
                        (SELECT a.attnum
                         FROM pg_attribute a
                         WHERE a.attrelid = t.oid
                           AND a.attname = 'symbol'
                           AND NOT a.attisdropped)
                      ]
            LOOP
                EXECUTE format('ALTER TABLE watchlist DROP CONSTRAINT %I', con.conname);
            END LOOP;
        END $$;
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_watchlist_user_symbol "
        "ON watchlist (user_id, symbol)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_watchlist_user_id ON watchlist (user_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_watchlist_user_id")
    op.execute("DROP INDEX IF EXISTS uq_watchlist_user_symbol")
    op.execute("ALTER TABLE watchlist DROP COLUMN IF EXISTS user_id")
    op.execute("DROP INDEX IF EXISTS ix_alerts_user_id")
    op.execute("ALTER TABLE alerts DROP COLUMN IF EXISTS user_id")
    # The legacy UNIQUE(symbol) is not restored: it fails as soon as two users
    # share a symbol, which the upgrade explicitly allowed.
