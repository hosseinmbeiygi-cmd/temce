"""Alert engine: monitored instruments, analyses, notifications, settings, ledger.

Revision ID: 0127
Revises: 0126
Create Date: 2026-11-15

Backs ``services.alert_engine`` (the workflow behind the Alerts section). All tables are
new and additive; the only change to an existing table is one extra index on
``brsapi_option_snapshots``. The partial unique index on
``alert_monitors`` makes a duplicate active monitor for one (user, symbol) impossible,
which is what prevents duplicate monitoring work across restarts and concurrent requests.
"""

from __future__ import annotations

from alembic import op

revision = "0127"
down_revision = "0126"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_monitors (
            id VARCHAR(50) PRIMARY KEY,
            user_id VARCHAR(100) NOT NULL,
            symbol VARCHAR(60) NOT NULL,
            ins_id VARCHAR(40),
            isin VARCHAR(20),
            name VARCHAR(200),
            category VARCHAR(40) NOT NULL DEFAULT 'unknown',
            supported BOOLEAN NOT NULL DEFAULT false,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            monitoring_state VARCHAR(30) NOT NULL DEFAULT 'pending',
            identity TEXT,
            last_analysis_id VARCHAR(50),
            last_analyzed_at TIMESTAMPTZ,
            last_input_hash VARCHAR(64),
            last_error TEXT,
            removed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_alert_monitors_user_id ON alert_monitors (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_alert_monitors_ins_id ON alert_monitors (ins_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_alert_monitors_status ON alert_monitors (status)")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_alert_monitors_active "
        "ON alert_monitors (user_id, symbol) WHERE status = 'active'"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_analyses (
            id VARCHAR(50) PRIMARY KEY,
            monitor_id VARCHAR(50) NOT NULL,
            user_id VARCHAR(100) NOT NULL,
            symbol VARCHAR(60) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            valid_until TIMESTAMPTZ,
            state VARCHAR(30) NOT NULL,
            subject VARCHAR(30) NOT NULL DEFAULT 'new_position',
            regime VARCHAR(20),
            mode VARCHAR(20) NOT NULL DEFAULT 'paper',
            engine_version VARCHAR(40),
            rules_version VARCHAR(40),
            settings_version INTEGER,
            input_hash VARCHAR(64),
            supersedes_id VARCHAR(50),
            report TEXT NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_alert_analyses_monitor_id ON alert_analyses (monitor_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_alert_analyses_user_id ON alert_analyses (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_alert_analyses_created_at ON alert_analyses (created_at)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_notifications (
            id VARCHAR(50) PRIMARY KEY,
            user_id VARCHAR(100) NOT NULL,
            monitor_id VARCHAR(50),
            analysis_id VARCHAR(50),
            symbol VARCHAR(60),
            severity VARCHAR(20) NOT NULL,
            event_type VARCHAR(40) NOT NULL,
            title VARCHAR(300) NOT NULL,
            body TEXT,
            dedupe_key VARCHAR(200) NOT NULL,
            revises_id VARCHAR(50),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            valid_until TIMESTAMPTZ,
            telegram_state VARCHAR(20) NOT NULL DEFAULT 'not_requested',
            telegram_attempts INTEGER NOT NULL DEFAULT 0,
            telegram_error TEXT,
            telegram_at TIMESTAMPTZ,
            acknowledged_at TIMESTAMPTZ,
            CONSTRAINT uq_alert_notifications_dedupe UNIQUE (user_id, dedupe_key)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_alert_notifications_user_id ON alert_notifications (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_alert_notifications_monitor_id ON alert_notifications (monitor_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_alert_notifications_created_at ON alert_notifications (created_at)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_engine_settings (
            id BIGSERIAL PRIMARY KEY,
            user_id VARCHAR(100) NOT NULL,
            version INTEGER NOT NULL,
            settings TEXT NOT NULL,
            approved_by VARCHAR(100),
            note TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_alert_engine_settings_version UNIQUE (user_id, version)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_alert_engine_settings_user_id ON alert_engine_settings (user_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_ledger_entries (
            id VARCHAR(50) PRIMARY KEY,
            user_id VARCHAR(100) NOT NULL,
            entry_type VARCHAR(20) NOT NULL,
            book VARCHAR(10) NOT NULL DEFAULT 'actual',
            symbol VARCHAR(60),
            quantity DOUBLE PRECISION,
            price_rial DOUBLE PRECISION,
            fees_toman DOUBLE PRECISION DEFAULT 0,
            amount_toman DOUBLE PRECISION,
            executed_at TIMESTAMPTZ NOT NULL,
            analysis_id VARCHAR(50),
            note TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_alert_ledger_type CHECK (entry_type IN ('buy','sell','deposit','withdrawal')),
            CONSTRAINT ck_alert_ledger_book CHECK (book IN ('actual','paper'))
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_alert_ledger_entries_user_id ON alert_ledger_entries (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_alert_ledger_entries_symbol ON alert_ledger_entries (symbol)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_equity_state (
            user_id VARCHAR(100) NOT NULL,
            book VARCHAR(10) NOT NULL,
            hwm_toman DOUBLE PRECISION NOT NULL,
            hwm_flows_toman DOUBLE PRECISION NOT NULL DEFAULT 0,
            last_equity_toman DOUBLE PRECISION,
            updated_at TIMESTAMPTZ,
            PRIMARY KEY (user_id, book)
        )
        """
    )

    # Related options are linked to an underlying by its identifier (never by name);
    # without this index that lookup is a 20s+ sequential scan of the option snapshots.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_option_underlying_id_fetched "
        "ON brsapi_option_snapshots (underlying_id, fetched_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_option_underlying_id_fetched")
    for table in ("alert_equity_state", "alert_ledger_entries", "alert_engine_settings",
                  "alert_notifications", "alert_analyses", "alert_monitors"):
        op.execute(f"DROP TABLE IF EXISTS {table}")
