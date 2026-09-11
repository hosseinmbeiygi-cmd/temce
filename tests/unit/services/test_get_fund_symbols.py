"""Unit tests for ``BrsApiSyncService._get_fund_symbols``.

Covers:
  - Only fund/ETF sector symbols are returned (stocks excluded)
  - Insurance/pension sectors excluded even when they contain "صندوق"
  - Arabic yeh/kaf normalised so same fund is never listed twice
  - Curated ``BRSAPI_ETF_SYMBOLS`` list is merged when symbols exist in DB
  - Curated entries NOT present in DB snapshots are dropped
  - DB exception gracefully falls back to curated list
  - Empty DB returns only curated symbols that happen to exist

No network or real database — everything is mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from brsapi.services.sync_service import (
    BrsApiSyncService,
    _dedupe_symbols,
    _normalize_persian,
    fund_sector_sql_condition,
    is_fund_sector,
)

# ── Helpers ────────────────────────────────────────────────────────────────


def _make_session(rows: list[tuple[str]]) -> MagicMock:
    """Create a mock ``AsyncSession`` that returns *rows* from ``session.execute``."""
    session = MagicMock()
    result = MagicMock()
    result.fetchall.return_value = rows
    session.execute = AsyncMock(return_value=result)
    return session


def _make_broken_session() -> MagicMock:
    """Session whose ``execute`` always raises (simulates missing table, etc.)."""
    session = MagicMock()
    session.execute = AsyncMock(side_effect=RuntimeError("table not found"))
    return session


def _service() -> BrsApiSyncService:
    return BrsApiSyncService(client=MagicMock(), session=MagicMock())


# ── Tests ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_returns_only_fund_sector_symbols():
    """Symbols whose sector matches صندوق/fund/etf are returned."""
    session = _make_session(
        [
            ("آگاس",),
            ("سهامدار",),
            ("horizon",),
        ]
    )
    result = await _service()._get_fund_symbols(session)
    assert "آگاس" in result
    assert "سهامدار" in result
    assert "horizon" in result


@pytest.mark.asyncio
async def test_excludes_insurance_pension_sectors():
    """Insurance sectors containing 'بیمه' must be excluded even if sector also has 'صندوق'.

    The SQL ``WHERE`` clause uses ``~sector_col.ilike('%بیمه%')`` to drop
    insurance/pension rows at the DB level.  Our mock can't evaluate SQL,
    so we simulate what the DB would return *after* the filter is applied:
    only genuine fund symbols come back.
    """
    # After the DB-level filter, only fund symbols remain:
    session = _make_session(
        [
            ("صندوق_سهامی",),
            ("صندوق_طلا",),
            ("سهامدار",),
        ]
    )
    result = await _service()._get_fund_symbols(session)
    # All returned symbols must be present
    assert "صندوق_سهامی" in result
    assert "صندوق_طلا" in result
    assert "سهامدار" in result
    # Confirm no insurance symbol leaked in (the mock already simulates
    # the filtered result, so this assertion documents the expectation)
    assert all("بیمه" not in s for s in result), f"Insurance symbol leaked: {[s for s in result if 'بیمه' in s]}"


@pytest.mark.asyncio
async def test_arabic_persian_dedup():
    """Same fund written with Arabic ي (U+064A) or Persian ی (U+06CC) appears only once."""
    # Arabic yeh: بيدار  |  Persian yeh: بیدار
    arabic = "بيدار"  # \u0628\u064a\u062f\u0627\u0631
    persian = "بیدار"  # \u0628\u06cc\u062f\u0627\u0631

    # DB returns the Persian form
    session = _make_session([(persian,)])
    # Curated list has the Arabic form (as it historically does)
    with patch(
        "brsapi.services.sync_service.BRSAPI_ETF_SYMBOLS",
        [arabic, "some_other_fund"],
    ):
        result = await _service()._get_fund_symbols(session)

    # Only one occurrence of بیدار should exist (not both forms)
    normalized = [_normalize_persian(s) for s in result]
    assert normalized.count(_normalize_persian(persian)) == 1, (
        f"Fund appears {normalized.count(_normalize_persian(persian))} times — expected exactly 1"
    )


@pytest.mark.asyncio
async def test_curated_list_filtered_to_known_symbols():
    """Curated symbols NOT in DB snapshots are excluded."""
    session = _make_session(
        [
            ("آگاس",),
            ("سهامدار",),
        ]
    )
    with patch(
        "brsapi.services.sync_service.BRSAPI_ETF_SYMBOLS",
        ["آگاس", "سهامدار", "نماد_خیالی_که_در_دیتابیس_نیست"],
    ):
        result = await _service()._get_fund_symbols(session)

    assert "آگاس" in result
    assert "سهامدار" in result
    assert "نماد_خیالی_که_در_دیتابیس_نیست" not in result


@pytest.mark.asyncio
async def test_curated_list_supplements_db_results():
    """Curated ETF symbols present in the DB (via sector query) are included.

    The curated list acts as a union: symbols from BRSAPI_ETF_SYMBOLS that
    also exist in the DB snapshot results are added to the output.  This
    ensures newly-listed funds whose sector might be slightly different
    still get synced as long as they appear in the snapshots table.
    """
    session = _make_session(
        [
            ("آگاس",),
        ]
    )
    with patch(
        "brsapi.services.sync_service.BRSAPI_ETF_SYMBOLS",
        ["آگاس", "سهامدار"],
    ):
        result = await _service()._get_fund_symbols(session)

    assert "آگاس" in result
    # "سهامدار" is NOT in DB results → not in db_set → not in curated_known
    assert "سهامدار" not in result, "Symbol only in curated list but not in DB should be excluded"


@pytest.mark.asyncio
async def test_curated_list_includes_symbol_also_in_db():
    """A curated symbol that also appears in DB results is included."""
    session = _make_session(
        [
            ("آگاس",),
            ("سهامدار",),
        ]
    )
    with patch(
        "brsapi.services.sync_service.BRSAPI_ETF_SYMBOLS",
        ["آگاس", "سهامدار"],
    ):
        result = await _service()._get_fund_symbols(session)

    assert "آگاس" in result
    assert "سهامدار" in result


@pytest.mark.asyncio
async def test_db_exception_falls_back_to_empty():
    """If the DB query fails, the method should not crash and return an empty list
    (no curated symbols match because the DB set is empty)."""
    session = _make_broken_session()
    result = await _service()._get_fund_symbols(session)
    # No DB symbols → db_set is empty → curated list has nothing to match
    assert result == []


@pytest.mark.asyncio
async def test_empty_db_returns_empty():
    """When DB has no fund symbols and curated list has no match, result is empty."""
    session = _make_session([])
    with patch(
        "brsapi.services.sync_service.BRSAPI_ETF_SYMBOLS",
        ["some_symbol_not_in_db"],
    ):
        result = await _service()._get_fund_symbols(session)
    assert result == []


@pytest.mark.asyncio
async def test_none_and_empty_symbols_filtered():
    """None or empty-string symbols from DB are silently dropped."""
    session = _make_session(
        [
            ("آگاس",),
            (None,),
            ("",),
            ("   ",),
            ("سهامدار",),
        ]
    )
    result = await _service()._get_fund_symbols(session)
    assert "" not in result
    assert None not in result
    # Whitespace-only is stripped to "" by _dedupe_symbols, which drops it
    assert "آگاس" in result
    assert "سهامدار" in result


@pytest.mark.asyncio
async def test_dedup_preserves_first_occurrence():
    """When a symbol appears in both DB and curated lists, only the first
    (DB-discovered) occurrence is kept, preserving order."""
    session = _make_session(
        [
            ("نماد_اول",),
            ("نماد_دوم",),
        ]
    )
    with patch(
        "brsapi.services.sync_service.BRSAPI_ETF_SYMBOLS",
        ["نماد_اول", "نماد_دوم"],
    ):
        result = await _service()._get_fund_symbols(session)

    # Both symbols should appear exactly once despite being in both sources
    assert result.count("نماد_اول") == 1
    assert result.count("نماد_دوم") == 1
    # DB order preserved
    assert result.index("نماد_اول") < result.index("نماد_دوم")


# ── Helper unit tests ──────────────────────────────────────────────────────


class TestNormalizePersian:
    def test_arabic_yeh_to_persian(self):
        assert _normalize_persian("بيدار") == "بیدار"

    def test_arabic_kaf_to_persian(self):
        assert _normalize_persian("كريم") == "کریم"

    def test_already_persian(self):
        assert _normalize_persian("بیدار") == "بیدار"

    def test_empty_string(self):
        assert _normalize_persian("") == ""


class TestDedupeSymbols:
    def test_removes_duplicates(self):
        assert _dedupe_symbols(["A", "A", "B"]) == ["A", "B"]

    def test_strips_whitespace(self):
        assert _dedupe_symbols(["  A  ", "A"]) == ["A"]

    def test_drops_empty_and_none(self):
        assert _dedupe_symbols(["A", "", None, "  ", "B"]) == ["A", "B"]

    def test_preserves_order(self):
        assert _dedupe_symbols(["C", "A", "B", "A"]) == ["C", "A", "B"]


# ── Fund-sector classification ─────────────────────────────────────────────


class TestIsFundSector:
    def test_accepts_fund_and_etf_sectors(self):
        assert is_fund_sector("صندوق سهامی اهرم")
        assert is_fund_sector("ETF الماس")
        assert is_fund_sector("Equity Fund")

    def test_rejects_insurance_pension_sectors(self):
        # These sectors contain "صندوق" but are not tradable funds.
        assert not is_fund_sector("بیمه و صندوق بازنشستگی")
        assert not is_fund_sector("صندوق بازنشستگی تکمیلی")
        assert not is_fund_sector("بیمه ایران")

    def test_rejects_non_fund_sectors(self):
        assert not is_fund_sector("فلزات اساسی")
        assert not is_fund_sector("بانک ملت")
        assert not is_fund_sector("")
        assert not is_fund_sector(None)


class TestFundSectorSqlCondition:
    def _compiled(self) -> str:
        from sqlalchemy import select
        from sqlalchemy.dialects import postgresql

        from brsapi.models import SymbolSnapshotModel

        stmt = select(SymbolSnapshotModel.symbol).where(
            fund_sector_sql_condition(SymbolSnapshotModel.sector)
        )
        return str(
            stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        )

    def test_compiled_sql_excludes_insurance_and_pension(self):
        sql = self._compiled()
        assert "بیمه" in sql
        assert "بازنشستگی" in sql
        # The old single-condition query only filtered "بیمه", so this is the
        # regression guard for the "صندوق بازنشستگی تکمیلی" leak.
        assert sql.count("NOT ILIKE") >= 2

    def test_compiled_sql_matches_funds(self):
        sql = self._compiled()
        assert "صندوق" in sql
        assert "fund" in sql
        assert "etf" in sql

    @pytest.mark.asyncio
    async def test_condition_executes_against_real_rows(self):
        """Run the generated SQL against SQLite to prove pension rows are filtered."""
        from sqlalchemy import column, table, text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        symbols_table = table("symbols", column("symbol"), column("sector"))
        rows = [
            ("اهرم", "صندوق سهامی اهرم"),
            ("بیمه1", "بیمه و صندوق بازنشستگی"),
            ("بیمه2", "صندوق بازنشستگی تکمیلی"),
            ("فملی", "فلزات اساسی"),
        ]

        async with engine.begin() as conn:
            await conn.execute(
                text("CREATE TABLE symbols (symbol TEXT, sector TEXT)")
            )
            await conn.execute(
                symbols_table.insert(),
                [{"symbol": s, "sector": sec} for s, sec in rows],
            )
            result = await conn.execute(
                symbols_table.select()
                .with_only_columns(symbols_table.c.symbol)
                .where(fund_sector_sql_condition(symbols_table.c.sector))
            )
            returned = {row[0] for row in result.fetchall()}

        await engine.dispose()
        assert returned == {"اهرم"}

    @pytest.mark.asyncio
    async def test_nav_symbol_query_uses_shared_condition(self):
        """``_get_fund_symbols`` must build its sector query from the shared rule."""
        from sqlalchemy.dialects import postgresql

        captured: dict[str, object] = {}
        session = MagicMock()
        result = MagicMock()
        result.fetchall.return_value = []

        async def execute(stmt, *args, **kwargs):
            captured.setdefault("stmt", stmt)
            return result

        session.execute = execute

        with patch(
            "brsapi.services.sync_service.fund_sector_sql_condition",
            wraps=fund_sector_sql_condition,
        ) as spy:
            await _service()._get_fund_symbols(session)

        assert spy.called, "NAV symbol query must use the shared fund-sector condition"
        sql = str(
            captured["stmt"].compile(  # type: ignore[union-attr]
                dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
            )
        )
        assert "بازنشستگی" in sql
        assert "بیمه" in sql
