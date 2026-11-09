"""Phase 1 — GOLD_TEST_DATABASE_URL allowlist guard.

The brief requires that needs_db tests for gold paths can ONLY run against an
explicitly allowlisted test host and database name:
  - GOLD_TEST_DB_ALLOWED_HOSTS: comma-separated list of allowed DB hosts
  - GOLD_TEST_DB_ALLOWED_NAMES: comma-separated list of allowed DB names
  - URL must differ from the app's DATABASE_URL
  - DB name must contain the substring 'test'

Fail closed (return False / skip message) if any check cannot be verified.
Never print the URL or credentials.

RED: the guard function does not exist yet.
GREEN: after adding validate_gold_test_db_url() to tests/conftest.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_guard_function_exists():
    """conftest must export validate_gold_test_db_url."""
    import tests.conftest as cf  # noqa: F401

    assert hasattr(cf, "validate_gold_test_db_url"), (
        "tests.conftest must define validate_gold_test_db_url(url, app_url) -> bool | str"
    )


def test_rejects_no_test_in_name():
    """DB name without 'test' is rejected."""
    from tests.conftest import validate_gold_test_db_url

    url = "postgresql+asyncpg://u:p@localhost:5432/production_db"
    app = "postgresql+asyncpg://u:p@localhost:5432/market"
    result = validate_gold_test_db_url(url, app_url=app,
                                       allowed_hosts={"localhost"},
                                       allowed_names={"gold_test"})
    assert result is not True, "Must reject: DB name 'production_db' has no 'test' substring"


def test_rejects_host_not_in_allowlist():
    """DB host not in allowed_hosts is rejected."""
    from tests.conftest import validate_gold_test_db_url

    url = "postgresql+asyncpg://u:p@db.production.example.com:5432/gold_test"
    app = "postgresql+asyncpg://u:p@localhost:5432/market"
    result = validate_gold_test_db_url(url, app_url=app,
                                       allowed_hosts={"localhost", "127.0.0.1"},
                                       allowed_names={"gold_test"})
    assert result is not True, "Must reject: host not in allowlist"


def test_rejects_same_as_app_url():
    """Test URL equal to app URL is rejected (would hit production DB)."""
    from tests.conftest import validate_gold_test_db_url

    url = "postgresql+asyncpg://u:p@localhost:5432/market"
    result = validate_gold_test_db_url(url, app_url=url,
                                       allowed_hosts={"localhost"},
                                       allowed_names={"market"})
    assert result is not True, "Must reject: test URL is identical to app URL"


def test_accepts_valid_test_url():
    """A properly configured gold test URL passes all checks."""
    from tests.conftest import validate_gold_test_db_url

    url = "postgresql+asyncpg://u:p@localhost:5432/gold_test"
    app = "postgresql+asyncpg://u:p@localhost:5432/market"
    result = validate_gold_test_db_url(url, app_url=app,
                                       allowed_hosts={"localhost"},
                                       allowed_names={"gold_test"})
    assert result is True, f"Should accept a valid test URL; got: {result!r}"
