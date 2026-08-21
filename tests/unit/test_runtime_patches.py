"""Regression tests for the three surgical runtime patches.

1. ``core.time.now_iran`` exists and returns an Iran-tz datetime (fixes the
   ImportError in the pipeline enrichment modules).
2. ``datetime.utcnow()`` is gone from monitoring/ and providers/manual/
   (deprecated in Python 3.12).
3. ``SQLMapping.create_table_sql`` is dialect-aware: ``SERIAL`` for
   PostgreSQL, ``AUTOINCREMENT`` for SQLite.
"""

from __future__ import annotations


def test_now_iran_exists_and_is_tehran_tz() -> None:
    from datetime import datetime

    from core.time import now_iran, now_tehran

    dt = now_iran()
    assert isinstance(dt, datetime)
    assert dt.tzinfo is not None
    assert str(dt.tzinfo) == "Asia/Tehran"
    # Same instant as now_tehran (alias)
    assert abs((now_tehran() - dt).total_seconds()) < 2


def test_pipeline_enrichment_modules_import() -> None:
    """The 5 modules that import now_iran must import without error."""
    import brsapi.pipelines.codal.enrichment  # noqa: F401
    import brsapi.pipelines.macro.enrichment  # noqa: F401
    import brsapi.pipelines.market.enrichment  # noqa: F401
    import brsapi.pipelines.market.persist  # noqa: F401
    import brsapi.pipelines.news.enrichment  # noqa: F401


def test_utcnow_removed_from_targeted_modules() -> None:
    """Deprecated utcnow() must not appear in monitoring/ or providers/manual/."""
    from pathlib import Path

    targets = [
        Path("monitoring/model_performance.py"),
        Path("monitoring/sla.py"),
        Path("providers/manual/manual_codal_provider.py"),
        Path("providers/manual/manual_macro_provider.py"),
        Path("providers/manual/manual_news_provider.py"),
        Path("providers/manual/manual_quote_provider.py"),
    ]
    for path in targets:
        src = path.read_text(encoding="utf-8")
        assert "utcnow" not in src, f"{path} still uses datetime.utcnow()"


def test_utcnow_replaced_with_aware_utc() -> None:
    """The replaced calls must produce tz-aware UTC timestamps."""
    import asyncio

    from providers.manual.manual_quote_provider import ManualQuoteProvider

    async def _run() -> dict:
        p = ManualQuoteProvider()
        result = await p.submit(data={
            "symbol": "ABC",
            "date": "2026-08-18",
            "open": 98, "high": 102, "low": 97, "close": 100,
            "volume": 10, "value": 1000, "count": 5,
        })
        assert result.success
        submitted = result.value
        assert submitted is not None
        return submitted

    submitted = asyncio.run(_run())
    assert submitted["submitted_at"].endswith("+00:00")


def test_create_table_sql_postgresql_uses_serial() -> None:
    from providers.historical.sql_database.mapping import SQLMapping

    ddl = SQLMapping(dialect="postgresql").create_table_sql()
    assert "id SERIAL PRIMARY KEY" in ddl
    assert "AUTOINCREMENT" not in ddl


def test_create_table_sql_sqlite_uses_autoincrement() -> None:
    from providers.historical.sql_database.mapping import SQLMapping

    ddl = SQLMapping(dialect="sqlite").create_table_sql()
    assert "id INTEGER PRIMARY KEY AUTOINCREMENT" in ddl


def test_sql_database_provider_detects_dialect() -> None:
    from providers.historical.sql_database.provider import SQLDatabaseProvider

    pg = SQLDatabaseProvider(url="postgresql+asyncpg://u:p@h/db")
    assert pg.mapping.dialect == "postgresql"

    sqlite = SQLDatabaseProvider(url="sqlite+aiosqlite:///tmp/x.db")
    assert sqlite.mapping.dialect == "sqlite"
