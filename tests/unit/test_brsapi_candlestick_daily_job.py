"""Unit tests for the daily full-market candlestick backfill job.

Covers the ``brsapi_candlesticks_all`` job registration (daily 13:00 cron)
and the ``_run_candlesticks_all`` orchestration:

1. The job is registered enabled with the after-close cron.
2. The backfill refreshes AllSymbols, prioritises symbols without
   candlestick rows, bounds the daily chunk via env, and syncs all three
   candle types (3=adjusted, 2=unadjusted, 1=realtime).
"""

from unittest.mock import AsyncMock

import pytest

from brsapi.jobs.registry import BrsApiJobRegistry, BrsApiSyncJob
from brsapi.services.sync_service import SyncReport


@pytest.fixture(autouse=True)
def _no_tehran_weekend(monkeypatch):
    """Pin the Tehran weekend guard off by default.

    These tests exercise candlestick backfill logic, not the weekend guard
    (the dedicated weekend tests patch ``_is_tehran_weekend`` themselves,
    overriding this fixture). Without this pin the suite fails whenever it
    runs on a Thursday/Friday.
    """
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod, "_is_tehran_weekend", lambda: False)


# ── Job registration ──────────────────────────────────────────────────


def test_candlesticks_all_job_registered_enabled_with_after_close_cron():
    registry = BrsApiJobRegistry()
    registry.register(BrsApiSyncJob(
        name="brsapi_candlesticks_all",
        endpoint_config=object(),  # type: ignore[arg-type]
        cron="0 13 * * *",
        description="Daily 13:00 candlestick backfill",
    ))
    job = registry.get("brsapi_candlesticks_all")
    assert job is not None
    assert job.enabled is True
    assert job.cron == "0 13 * * *"


async def test_run_candlesticks_all_skips_tehran_weekend(monkeypatch):
    """On Thursday/Friday (Tehran weekend) the backfill returns early with
    skipped=True and makes NO API calls — the free quota is conserved."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod, "_is_tehran_weekend", lambda: True)

    registry = BrsApiJobRegistry()
    service = AsyncMock()
    session = AsyncMock()
    session.commit = AsyncMock()

    report = await registry._run_candlesticks_all(session, service)

    assert report is not None
    assert report.skipped is True
    assert report.items_count == 0
    # No AllSymbols refresh, no candlestick syncs on the weekend.
    service.sync_all_symbols.assert_not_called()
    service.sync_candlesticks.assert_not_called()
    session.execute.assert_not_called()


async def test_run_candlesticks_all_skips_when_allsymbols_empty(monkeypatch):
    """If the fresh AllSymbols fetch succeeds but returns zero symbols the
    market is closed/holiday — the candle backfill is skipped entirely and
    NO candlestick requests are made (stale symbol list is not reused)."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod, "_is_tehran_weekend", lambda: False)

    registry = BrsApiJobRegistry()
    service = AsyncMock()
    service.sync_all_symbols = AsyncMock(return_value=SyncReport(
        endpoint="/Tsetmc/AllSymbols.php", success=True, items_count=0,
    ))
    service.sync_candlesticks = AsyncMock()
    session = AsyncMock()
    session.commit = AsyncMock()

    report = await registry._run_candlesticks_all(session, service)

    assert report is not None
    assert report.skipped is True
    assert report.items_count == 0
    # No candle syncs on a market holiday.
    service.sync_candlesticks.assert_not_called()
    session.execute.assert_not_called()


async def test_run_candlesticks_all_proceeds_when_allsymbols_fetch_fails(monkeypatch):
    """A failed AllSymbols fetch (API/network error) is NOT treated as a
    holiday — the backfill proceeds using the symbol list already in the
    snapshots table."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod, "_is_tehran_weekend", lambda: False)
    monkeypatch.setattr(reg_mod.brsapi_settings, "candle_req_delay", 0)

    registry = BrsApiJobRegistry()
    service = AsyncMock()
    service.sync_all_symbols = AsyncMock(return_value=SyncReport(
        endpoint="/Tsetmc/AllSymbols.php", success=False,
        error="HTTP 502", items_count=0,
    ))
    service.sync_candlesticks = AsyncMock(return_value=SyncReport(
        endpoint="/Tsetmc/Candlestick.php", success=True, items_count=100,
    ))

    class _FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def __iter__(self):
            return iter(self._rows)

        def fetchall(self):
            return self._rows

    session = AsyncMock()

    async def _execute(stmt):
        text = str(stmt)
        if "brsapi_candlesticks" in text:
            return _FakeResult([])
        return _FakeResult([("فولاد",), ("فملی",)])

    session.execute = _execute
    session.commit = AsyncMock()

    report = await registry._run_candlesticks_all(session, service)

    assert report is not None
    assert report.skipped is not True
    assert report.items_count == 600          # 2 x 3 x 100 — proceeded
    service.sync_candlesticks.assert_awaited()


# ── Orchestration ─────────────────────────────────────────────────────


async def test_run_candlesticks_all_prioritises_missing_and_syncs_all_types(monkeypatch):
    """Symbols without candlestick rows come first; every symbol in the
    daily chunk gets types 3, 2 and 1."""
    import brsapi.jobs.registry as reg_mod

    # Speed up the test — no delay between requests.
    monkeypatch.setattr(reg_mod.brsapi_settings, "candle_req_delay", 0)

    registry = BrsApiJobRegistry()
    service = AsyncMock()
    service.sync_all_symbols = AsyncMock(return_value=SyncReport(
        endpoint="/Tsetmc/AllSymbols.php", success=True, items_count=10,
    ))
    service.sync_candlesticks = AsyncMock(return_value=SyncReport(
        endpoint="/Tsetmc/Candlestick.php", success=True, items_count=100,
    ))

    symbols = ["فولاد", "فملی", "شپنا"]
    have = {"فولاد"}  # only فولاد already synced

    class _FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def __iter__(self):
            return iter(self._rows)

        def fetchall(self):
            return self._rows

    session = AsyncMock()
    query_results = {
        # snapshot symbols query -> all symbols
        "snapshots": [(s,) for s in symbols],
        # candlestick symbols query -> already-synced symbols
        "candles": [(s,) for s in sorted(have)],
    }
    query_log: list[str] = []

    async def _execute(stmt):
        # Distinguish queries by which model they reference.
        text = str(stmt)
        if "brsapi_candlesticks" in text:
            query_log.append("candles")
            return _FakeResult(query_results["candles"])
        query_log.append("snapshots")
        return _FakeResult(query_results["snapshots"])

    session.execute = _execute
    session.commit = AsyncMock()

    report = await registry._run_candlesticks_all(session, service)

    assert report is not None
    assert report.success is True
    # 3 symbols in the daily chunk x 3 types x 100 items
    assert report.items_count == 900

    # Order: missing symbols first, then already-synced ones.
    called_symbols = [c.args[1] for c in service.sync_candlesticks.call_args_list]
    assert called_symbols[0] == "فملی" or called_symbols[0] == "شپنا"
    assert called_symbols[-1] == "فولاد"
    # 9 sync calls: 3 symbols x 3 types
    assert len(service.sync_candlesticks.call_args_list) == 9
    # Every symbol got all three types
    for c in service.sync_candlesticks.call_args_list:
        assert c.kwargs["candle_type"] in ("3", "2", "1")

    # AllSymbols refresh happened first
    service.sync_all_symbols.assert_awaited_once()


async def test_run_candlesticks_all_bounds_chunk_by_settings(monkeypatch):
    """candle_daily_max_symbols caps the per-day chunk."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod.brsapi_settings, "candle_daily_max_symbols", 1)
    # Speed up the test — no delay between requests.
    monkeypatch.setattr(reg_mod.brsapi_settings, "candle_req_delay", 0)

    registry = BrsApiJobRegistry()
    service = AsyncMock()
    service.sync_all_symbols = AsyncMock(return_value=SyncReport(
        endpoint="/Tsetmc/AllSymbols.php", success=True, items_count=10,
    ))
    service.sync_candlesticks = AsyncMock(return_value=SyncReport(
        endpoint="/Tsetmc/Candlestick.php", success=True, items_count=5,
    ))

    class _FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def __iter__(self):
            return iter(self._rows)

        def fetchall(self):
            return self._rows

    session = AsyncMock()

    async def _execute(stmt):
        text = str(stmt)
        if "brsapi_candlesticks" in text:
            return _FakeResult([])
        return _FakeResult([("فولاد",), ("فملی",), ("شپنا",)])

    session.execute = _execute
    session.commit = AsyncMock()

    report = await registry._run_candlesticks_all(session, service)

    assert report is not None
    # Only 1 symbol x 3 types x 5 items
    assert report.items_count == 15
    assert len(service.sync_candlesticks.call_args_list) == 3
