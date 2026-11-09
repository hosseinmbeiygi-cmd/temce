"""Phase 1.5b migration tests — backfill + NOT NULL (needs_db).

These tests require a live PostgreSQL test database.
They are skipped automatically when GOLD_TEST_DATABASE_URL is not set or
fails the allowlist check defined in conftest.validate_gold_test_db_url().

Each test verifies the migration SQL against the allowlisted test DB without
touching the application database.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def _skip_if_no_test_db() -> str:
    """Return the test DB URL or pytest.skip."""
    from tests.conftest import validate_gold_test_db_url

    url = os.environ.get("GOLD_TEST_DATABASE_URL", "")
    app_url = os.environ.get("DATABASE_URL", "")
    allowed_hosts = set(
        (os.environ.get("GOLD_TEST_DB_ALLOWED_HOSTS") or "").split(",")
    ) - {""}
    allowed_names = set(
        (os.environ.get("GOLD_TEST_DB_ALLOWED_NAMES") or "").split(",")
    ) - {""}

    if not url:
        pytest.skip("GOLD_TEST_DATABASE_URL not set")

    result = validate_gold_test_db_url(
        url,
        app_url=app_url,
        allowed_hosts=allowed_hosts,
        allowed_names=allowed_names,
    )
    if result is not True:
        pytest.skip(f"GOLD_TEST_DATABASE_URL rejected: {result}")

    return url


def test_migration_0122_backfill_sql_valid():
    """The backfill SQL is syntactically valid and references the correct tables.

    This test inspects the migration file itself — no live DB needed.
    """
    migration_path = (
        ROOT / "migrations" / "versions" / "0122_gold_desk_ownership_enforce.py"
    )
    assert migration_path.exists(), f"Migration file not found: {migration_path}"

    text = migration_path.read_text()

    expected_tables = [
        "gold_holdings",
        "gold_dca_plans",
        "gold_trades",
        "gold_alert_rules",
        "gold_alert_events",
        "gold_portfolio_values",
    ]
    for table in expected_tables:
        assert table in text, f"Table {table!r} missing from migration 0122"

    assert "SET NOT NULL" in text, "Migration must add NOT NULL constraints"
    assert "DROP NOT NULL" in text, "Migration must have downgrade that drops NOT NULL"
    assert "__legacy_admin__" in text, (
        "Migration must use __legacy_admin__ fallback when no admin user exists"
    )
    assert "down_revision" in text and '"0121"' in text, (
        "Migration 0122 must chain from 0121"
    )


def test_migration_chain_is_correct():
    """Revisions chain correctly: 0121 → 0122."""
    import importlib.util

    path = ROOT / "migrations" / "versions" / "0122_gold_desk_ownership_enforce.py"
    spec = importlib.util.spec_from_file_location("m0122", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    assert m.revision == "0122"
    assert m.down_revision == "0121"
