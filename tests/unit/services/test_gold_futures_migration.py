"""Migration test for the GoldDesk futures / kill-switch / journal tables (0114).

``models/gold.py`` declared these three tables without a matching migration, so
the futures endpoints raised ``UndefinedTableError`` on every call.  The
migration is applied to an in-memory SQLite database through Alembic's
``Operations`` context, validating real DDL + downgrade without PostgreSQL.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_ROOT = Path(__file__).resolve().parents[3] / "migrations" / "versions"

TABLES = [
    "gold_futures_positions",
    "gold_kill_switch_events",
    "gold_portfolio_holdings",
]


def _load_migration(name: str):
    path = _ROOT / name
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_0114_creates_gold_desk_futures_tables() -> None:
    module = _load_migration("0114_gold_futures_killswitch_holdings.py")
    assert module.revision == "0114"
    assert module.down_revision == "0113"

    engine = sa.create_engine("sqlite://")
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            module.upgrade()

        inspector = sa.inspect(connection)
        names = inspector.get_table_names()
        for table in TABLES:
            assert table in names, f"missing {table}"

        future_cols = {c["name"] for c in inspector.get_columns("gold_futures_positions")}
        assert {
            "id",
            "contract_symbol",
            "position_type",
            "leverage",
            "entry_price",
            "quantity",
            "initial_margin",
            "maintenance_margin",
            "liquidation_price",
            "opened_at",
            "status",
            "exit_price",
            "exit_reason",
        } <= future_cols

        holding_cols = {c["name"] for c in inspector.get_columns("gold_portfolio_holdings")}
        assert {"asset_symbol", "entry_price_irr", "status", "notes"} <= holding_cols

        ks_cols = {c["name"] for c in inspector.get_columns("gold_kill_switch_events")}
        assert {"triggered_at", "status", "rule", "reason", "metrics"} <= ks_cols

        # Re-running upgrade must not fail on an already-migrated database.
        with Operations.context(context):
            module.upgrade()

        with Operations.context(context):
            module.downgrade()

        remaining = sa.inspect(connection).get_table_names()
        for table in TABLES:
            assert table not in remaining, f"still present {table}"

    engine.dispose()
