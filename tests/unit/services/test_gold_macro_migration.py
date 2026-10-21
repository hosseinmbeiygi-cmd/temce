"""Migration tests for gold macro / calendar tables (revisions 0112, 0113).

Each migration is applied to an in-memory SQLite database through Alembic's
``Operations`` context, validating real DDL + downgrade without PostgreSQL.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

_ROOT = Path(__file__).resolve().parents[3] / "migrations" / "versions"


def _load_migration(name: str):
    path = _ROOT / name
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _upgrade_downgrade(module, expected_tables):
    engine = sa.create_engine("sqlite://")
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            module.upgrade()

        inspector = sa.inspect(connection)
        for table in expected_tables:
            assert table in inspector.get_table_names(), f"missing {table}"

        with Operations.context(context):
            module.downgrade()

        for table in expected_tables:
            assert table not in sa.inspect(connection).get_table_names(), f"still present {table}"

    engine.dispose()


def test_0112_creates_macro_indicators_and_cot_tables() -> None:
    module = _load_migration("0112_gold_macro_indicators_cot.py")
    assert module.revision == "0112"
    assert module.down_revision == "0111"

    _upgrade_downgrade(
        module,
        ["gold_macro_indicators", "gold_cot_positions"],
    )

    # Also verify upsert indexes exist after upgrade.
    engine = sa.create_engine("sqlite://")
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            module.upgrade()

        inspector = sa.inspect(connection)
        indexes = inspector.get_indexes("gold_macro_indicators")
        index_names = {ix["name"] for ix in indexes}
        assert "uq_gold_macro_indicators_as_of" in index_names

        indexes = inspector.get_indexes("gold_cot_positions")
        index_names = {ix["name"] for ix in indexes}
        assert "uq_gold_cot_positions_report_date" in index_names

        cols = {c["name"] for c in inspector.get_columns("gold_macro_indicators")}
        assert {"indicator", "as_of", "value", "fetched_at", "source"} <= cols

        cols = {c["name"] for c in inspector.get_columns("gold_cot_positions")}
        assert {"report_date", "managed_money_net", "fetched_at", "source"} <= cols

    engine.dispose()


def test_0113_creates_calendar_and_iran_tables() -> None:
    module = _load_migration("0113_gold_economic_calendar_iran.py")
    assert module.revision == "0113"
    assert module.down_revision == "0112"

    _upgrade_downgrade(
        module,
        ["gold_economic_calendar_events", "gold_iran_manual_events"],
    )

    engine = sa.create_engine("sqlite://")
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            module.upgrade()

        inspector = sa.inspect(connection)
        indexes = inspector.get_indexes("gold_economic_calendar_events")
        index_names = {ix["name"] for ix in indexes}
        assert "uq_gold_economic_calendar_event_id" in index_names

        indexes = inspector.get_indexes("gold_iran_manual_events")
        index_names = {ix["name"] for ix in indexes}
        assert "uq_gold_iran_manual_event_id" in index_names

        cols = {c["name"] for c in inspector.get_columns("gold_economic_calendar_events")}
        assert {"event_id", "event_date", "category", "is_high_volatility", "fetched_at"} <= cols

        cols = {c["name"] for c in inspector.get_columns("gold_iran_manual_events")}
        assert {"event_id", "event_date", "note", "is_high_volatility"} <= cols

    engine.dispose()
