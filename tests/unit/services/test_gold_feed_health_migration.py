"""Migration test for the gold feed health attempts table.

The migration is applied to an in-memory SQLite database through Alembic's
``Operations`` context. This validates the real DDL and the downgrade without
needing the project's PostgreSQL instance.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "migrations"
    / "versions"
    / "0111_gold_feed_health.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("gold_feed_health_migration", _MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_creates_and_drops_the_attempts_table() -> None:
    module = _load_migration()
    assert module.revision == "0111"
    assert module.down_revision == "0110"

    engine = sa.create_engine("sqlite://")
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            module.upgrade()

        inspector = sa.inspect(connection)
        assert "gold_feed_health_attempts" in inspector.get_table_names()

        columns = {column["name"] for column in inspector.get_columns("gold_feed_health_attempts")}
        assert {
            "id",
            "check_id",
            "provider",
            "status",
            "ok",
            "latency_ms",
            "age_seconds",
            "error",
            "price",
            "checked_at",
        } <= columns

        with Operations.context(context):
            module.downgrade()

        assert "gold_feed_health_attempts" not in sa.inspect(connection).get_table_names()

    engine.dispose()
