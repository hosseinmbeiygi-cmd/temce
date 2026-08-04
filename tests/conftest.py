"""Shared pytest configuration and environment fixes.

Auto-skip logic
---------------
Tests marked with ``@pytest.mark.needs_db`` are automatically skipped
when no PostgreSQL instance is reachable (checked once per session via
``pytest_collection_modifyitems``).  This lets developers run the
``tests/unit/`` suite locally without a running database while the full
suite (including DB-dependent tests) still runs in CI where
``services.postgres`` is configured.
"""

from __future__ import annotations

import asyncio
import os
import sys

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# ── UTF-8 reconfigure (Windows compat) ──────────────────────────
# On Windows the default console encoding (cp1252) cannot handle Persian text or
# emojis printed by some tests. Reconfigure stdout/stderr to UTF-8 so that
# collection and reporting do not crash with UnicodeEncodeError.


def _reconfigure_stream(stream):
    import contextlib

    with contextlib.suppress(AttributeError):
        # Python 3.7+ allows reconfiguring an existing TextIOWrapper.
        stream.reconfigure(encoding="utf-8", errors="replace")


_reconfigure_stream(sys.stdout)
_reconfigure_stream(sys.stderr)


# ── PostgreSQL availability check ───────────────────────────────
# Used by ``pytest_collection_modifyitems`` to skip ``needs_db`` tests
# when there is no reachable PostgreSQL instance.


def _db_url() -> str:
    """Return the DATABASE_URL to probe, falling back to localhost."""
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://market:market@localhost:5432/market_test",
    )


def _is_postgres_reachable() -> bool:
    """Return ``True`` iff PostgreSQL responds to ``SELECT 1``.

    The check is performed synchronously (``asyncio.run``) so it can
    be called from ``pytest_collection_modifyitems`` which is a
    synchronous hook.
    """
    db_url = _db_url()

    # SQLite is always "available" locally but is not real PostgreSQL;
    # tests that need *PostgreSQL* semantics (JSONB, TimescaleDB
    # hypertables, etc.) should not run on SQLite.
    if "sqlite" in db_url:
        return False

    async def _ping() -> bool:
        engine = create_async_engine(db_url)
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_ping())
    except Exception:
        return False


_DB_AVAILABLE: bool | None = None  # lazy cache, set once per session


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-skip ``@pytest.mark.needs_db`` tests when PostgreSQL is unreachable.

    The connectivity check runs **at most once** per session; the result
    is cached on ``config`` so that the same engine / ``asyncio.run``
    call is not repeated for every collected item.
    """
    global _DB_AVAILABLE  # noqa: PLW0603  — module-level cache is intentional

    if _DB_AVAILABLE is None:
        _DB_AVAILABLE = _is_postgres_reachable()

    if _DB_AVAILABLE:
        return  # no need to skip anything

    for item in items:
        if item.get_closest_marker("needs_db"):
            item.add_marker(
                pytest.mark.skip(
                    reason=(
                        "PostgreSQL is not reachable at "
                        f"{_db_url().split('@')[-1] if '@' in _db_url() else _db_url()}; "
                        "skipping test that requires a database"
                    )
                )
            )
