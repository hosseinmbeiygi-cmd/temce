"""Alembic home for service-private tables (audit run2, D4).

Several services own tables that are created with ``CREATE TABLE IF NOT EXISTS``
at runtime and are used with no ORM model and no migration:

* ``signal_performance`` / ``signal_weight_accuracy`` — services/signal_performance_tracker.py
* ``calibration_models``                              — services/probability_calibrator.py
* ``isotonic_calibration``                            — services/isotonic_calibrator.py
* ``diagnostic_runs`` / ``diagnostic_findings``       — services/diagnostics_runner.py

Runtime-only DDL means a clean production database (no ``create_all``, migrations
only) does not have them, and the first call fails with ``UndefinedTable``. This
migration gives every one of them a canonical home. The runtime ``CREATE TABLE IF
NOT EXISTS`` calls are intentionally left in place as a self-heal guard (they are
no-ops once the migration has run) — mirroring the watchlist pattern in 0117.

It also adds ``uq_signal_accuracy_pending_key``: the partial unique index the
quant orchestrator relied on existing (it is created at runtime in
``quant_signal_orchestrator._ensure_db_tables`` but was never in a migration).

All statements are ``IF NOT EXISTS`` and target PostgreSQL.

Revision ID: 0119
Revises: 0118
"""

from __future__ import annotations

from alembic import op

revision = "0119_service_private_tables"
down_revision = "0118_core_tables_backfill"
branch_labels = None
depends_on = None


# (table_name, "CREATE TABLE IF NOT EXISTS ...") - frozen from the service DDL,
# 2026-10-29. tests/unit/test_service_private_tables_migration.py fails if this
# diverges from the service source.
_TABLES: tuple[tuple[str, str], ...] = (
    (
        "signal_performance",
        """CREATE TABLE IF NOT EXISTS signal_performance (
    id SERIAL PRIMARY KEY,
    signal_id VARCHAR(64) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    direction VARCHAR(16) NOT NULL,
    entry_price NUMERIC NOT NULL,
    entry_date DATE NOT NULL,
    source VARCHAR(64) DEFAULT 'technical',
    check_3d_return NUMERIC,
    check_10d_return NUMERIC,
    was_correct_3d BOOLEAN,
    was_correct_10d BOOLEAN,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (signal_id)
)""",
    ),
    (
        "signal_weight_accuracy",
        """CREATE TABLE IF NOT EXISTS signal_weight_accuracy (
    id SERIAL PRIMARY KEY,
    source VARCHAR(64) NOT NULL,
    period VARCHAR(16) NOT NULL,
    total_signals INT DEFAULT 0,
    correct_signals INT DEFAULT 0,
    avg_return NUMERIC DEFAULT 0,
    weight NUMERIC DEFAULT 1.0,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (source, period)
)""",
    ),
    (
        "calibration_models",
        """CREATE TABLE IF NOT EXISTS calibration_models (
    id VARCHAR(100) PRIMARY KEY,
    market VARCHAR(50),
    timeframe VARCHAR(20),
    direction VARCHAR(10),
    regime VARCHAR(50),
    model_version VARCHAR(20),
    method VARCHAR(20),
    parameters TEXT,
    brier_score FLOAT,
    ece FLOAT,
    total_samples INTEGER DEFAULT 0,
    calibration_data TEXT,
    last_trained_at TIMESTAMP
)""",
    ),
    (
        "isotonic_calibration",
        """CREATE TABLE IF NOT EXISTS isotonic_calibration (
    id VARCHAR(150) PRIMARY KEY,
    market VARCHAR(50) NOT NULL,
    timeframe VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    n_samples INTEGER NOT NULL,
    brier_score FLOAT NOT NULL,
    ece FLOAT NOT NULL,
    buckets TEXT NOT NULL,
    trained_at TIMESTAMP NOT NULL
)""",
    ),
    (
        "diagnostic_runs",
        """CREATE TABLE IF NOT EXISTS diagnostic_runs (
    run_id VARCHAR(50) PRIMARY KEY,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    duration_seconds DOUBLE PRECISION,
    total_symbols INTEGER,
    total_findings INTEGER,
    critical_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    warning_count INTEGER DEFAULT 0,
    info_count INTEGER DEFAULT 0,
    health_status VARCHAR(20),
    summary JSONB
)""",
    ),
    (
        "diagnostic_findings",
        """CREATE TABLE IF NOT EXISTS diagnostic_findings (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(50) REFERENCES diagnostic_runs(run_id),
    level VARCHAR(20),
    category VARCHAR(50),
    symbol VARCHAR(50),
    message TEXT,
    details TEXT,
    strategy VARCHAR(50),
    duration_ms DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT NOW()
)""",
    ),
)

# Indexes created by the migrations above / for the canonical signal_accuracy table.
_INDEXES: tuple[tuple[str, str], ...] = (
    ("idx_diag_findings_run", "CREATE INDEX IF NOT EXISTS idx_diag_findings_run ON diagnostic_findings(run_id)"),
    ("idx_diag_findings_level", "CREATE INDEX IF NOT EXISTS idx_diag_findings_level ON diagnostic_findings(level)"),
    (
        "uq_signal_accuracy_pending_key",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_signal_accuracy_pending_key "
        "ON signal_accuracy (symbol, market, direction, timeframe) "
        "WHERE outcome_set_at IS NULL",
    ),
)


def upgrade() -> None:
    for _name, ddl in _TABLES:
        op.execute(ddl)
    for _name, ddl in _INDEXES:
        op.execute(ddl)


def downgrade() -> None:
    for name, _ddl in reversed(_INDEXES):
        op.execute(f'DROP INDEX IF EXISTS "{name}"')
    for name, _ddl in reversed(_TABLES):
        op.execute(f'DROP TABLE IF EXISTS "{name}"')
