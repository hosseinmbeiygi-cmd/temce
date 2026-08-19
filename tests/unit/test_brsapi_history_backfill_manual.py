"""Unit tests for the manual full-market history backfills.

Covers ``_run_history_price_all`` / ``_run_history_real_legal_all`` (both
delegated to the shared ``_run_history_backfill``) so the manage API can
trigger a whole-market history download from the UI — the same pattern
already exists for candlesticks and shareholders:

1. ``max_symbols=0`` means "no limit" (whole market) instead of the cap.
2. ``allow_weekend=True`` bypasses the Tehran weekend guard.
3. The ``progress`` dict receives live updates and can cancel the run.
4. An empty AllSymbols response (holiday) skips the backfill entirely.
5. An AllSymbols API failure still processes from the existing symbol list.
6. The status / cancel manage endpoints behave correctly for both backfills.
"""

from unittest.mock import AsyncMock

from apps.api.endpoints.brsapi import (
    _HISTORY_PRICE_BACKFILL_STATE,
    _HISTORY_REAL_LEGAL_BACKFILL_STATE,
    cancel_sync_all_history_price,
    cancel_sync_all_history_real_legal,
    sync_all_history_price_status,
    sync_all_history_real_legal_status,
)
from brsapi.jobs.registry import BrsApiJobRegistry
from brsapi.services.sync_service import SyncReport


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)

    def fetchall(self):
        return self._rows


def _make_session(symbols, have_price=None, have_rl=None):
    """Build a fake session whose execute() answers snapshot / history
    symbol queries. ``brsapi_historical_daily`` answers have_price and
    ``brsapi_historical_real_legal`` answers have_rl (symbols already synced)."""
    have_price = have_price or set()
    have_rl = have_rl or set()

    class _Session:
        def __init__(self):
            self.commit = AsyncMock()

        async def execute(self, stmt):
            text = str(stmt)
            if "brsapi_historical_daily" in text:
                return _FakeResult([(s,) for s in sorted(have_price)])
            if "brsapi_historical_real_legal" in text:
                return _FakeResult([(s,) for s in sorted(have_rl)])
            return _FakeResult([(s,) for s in symbols])

    return _Session()


def _make_service(ok=True, items=15, symbols_count=10):
    service = AsyncMock()
    service.sync_all_symbols = AsyncMock(return_value=SyncReport(
        endpoint="/Tsetmc/AllSymbols.php", success=True, items_count=symbols_count,
    ))
    service.sync_history_price = AsyncMock(return_value=SyncReport(
        endpoint="/Tsetmc/History.php", success=ok, items_count=items,
    ))
    service.sync_history_real_legal = AsyncMock(return_value=SyncReport(
        endpoint="/Tsetmc/History_RealLegal.php", success=ok, items_count=items,
    ))
    return service


# ── Whole-market download (max_symbols=0) ─────────────────────────────


async def test_history_price_backfill_max_symbols_zero_processes_all(monkeypatch):
    """max_symbols=0 (manual "download all symbols") is NOT capped by the
    settings default — every symbol in the market is processed."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod.brsapi_settings, "history_price_daily_max_symbols", 1)
    monkeypatch.setattr(reg_mod.brsapi_settings, "history_price_req_delay", 0)

    registry = BrsApiJobRegistry()
    session = _make_session(["فولاد", "فملی", "شپنا", "خودرو", "وبملت"])
    service = _make_service()

    report = await registry._run_history_price_all(session, service, max_symbols=0)

    assert report is not None
    assert report.success is True
    # All 5 symbols x 15 records
    assert report.items_count == 75
    assert len(service.sync_history_price.call_args_list) == 5


async def test_history_real_legal_backfill_max_symbols_override(monkeypatch):
    """A positive max_symbols overrides the settings default for manual runs."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod.brsapi_settings, "history_real_legal_daily_max_symbols", 1000)
    monkeypatch.setattr(reg_mod.brsapi_settings, "history_real_legal_req_delay", 0)

    registry = BrsApiJobRegistry()
    session = _make_session(["فولاد", "فملی", "شپنا"])
    service = _make_service()

    report = await registry._run_history_real_legal_all(session, service, max_symbols=2)

    assert report is not None
    assert report.items_count == 30          # 2 x 15
    assert len(service.sync_history_real_legal.call_args_list) == 2


# ── Missing-first ordering ────────────────────────────────────────────


async def test_history_backfill_missing_symbols_processed_first(monkeypatch):
    """Symbols without any history rows are processed before already-synced ones."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod.brsapi_settings, "history_price_req_delay", 0)

    registry = BrsApiJobRegistry()
    symbols = ["فولاد", "فملی", "شپنا"]
    session = _make_session(symbols, have_price={"فملی", "شپنا"})  # فولاد missing
    service = _make_service()

    report = await registry._run_history_price_all(session, service, max_symbols=0)

    assert report is not None
    assert report.items_count == 45          # 3 x 15
    called = [c.args[1] for c in service.sync_history_price.call_args_list]
    assert called == ["فولاد", "فملی", "شپنا"]  # missing first


# ── Weekend override ──────────────────────────────────────────────────


async def test_history_backfill_allow_weekend_bypasses_guard(monkeypatch):
    """Manual runs pass allow_weekend=True so an admin can always
    download data, even on a Tehran weekend."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod, "_is_tehran_weekend", lambda: True)
    monkeypatch.setattr(reg_mod.brsapi_settings, "history_price_req_delay", 0)

    registry = BrsApiJobRegistry()
    session = _make_session(["فولاد", "فملی"])
    service = _make_service()

    report = await registry._run_history_price_all(session, service, allow_weekend=True)

    assert report is not None
    assert report.skipped is not True
    assert report.items_count == 30          # 2 x 15
    service.sync_all_symbols.assert_awaited_once()


# ── Empty-market guard (holiday) ──────────────────────────────────────


async def test_history_backfill_skipped_on_empty_market(monkeypatch):
    """AllSymbols returning zero symbols (market closed/holiday) skips the
    whole backfill — no per-symbol requests are sent."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod.brsapi_settings, "history_price_req_delay", 0)

    registry = BrsApiJobRegistry()
    session = _make_session(["فولاد", "فملی"])
    service = _make_service(symbols_count=0)   # market closed
    progress: dict = {}

    report = await registry._run_history_price_all(session, service, progress=progress)

    assert report is not None
    assert report.skipped is True
    assert report.items_count == 0
    service.sync_history_price.assert_not_called()
    # The worker surfaces a holiday-specific message (not the weekend one).
    assert "بازار بسته/تعطیل" in progress["message"]


async def test_history_backfill_continues_on_symbols_api_error(monkeypatch):
    """An AllSymbols API failure (success=False) is NOT a holiday — the
    backfill proceeds using the existing symbol list."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod.brsapi_settings, "history_price_req_delay", 0)

    registry = BrsApiJobRegistry()
    session = _make_session(["فولاد", "فملی"])
    service = _make_service()
    service.sync_all_symbols = AsyncMock(return_value=SyncReport(
        endpoint="/Tsetmc/AllSymbols.php", success=False, items_count=0, error="boom",
    ))

    report = await registry._run_history_price_all(session, service)

    assert report is not None
    assert report.skipped is not True
    assert report.items_count == 30          # 2 x 15
    assert len(service.sync_history_price.call_args_list) == 2


# ── Progress reporting + cancellation ────────────────────────────────


async def test_history_backfill_reports_progress_and_cancels(monkeypatch):
    """The progress dict is updated live and setting cancel_requested
    stops the run after the current symbol."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod.brsapi_settings, "history_real_legal_req_delay", 0)

    registry = BrsApiJobRegistry()
    # 4 symbols; cancel after the 2nd completes.
    symbols = ["فولاد", "فملی", "شپنا", "خودرو"]
    session = _make_session(symbols)
    service = _make_service()

    progress: dict = {}
    calls = 0

    async def _tracking_sync(session_, symbol):
        nonlocal calls
        calls += 1
        # Cancel once two symbols are done.
        if calls == 2:
            progress["cancel_requested"] = True
        return SyncReport(
            endpoint="/Tsetmc/History_RealLegal.php", success=True, items_count=15,
        )

    service.sync_history_real_legal = _tracking_sync

    report = await registry._run_history_real_legal_all(
        session, service, max_symbols=0, progress=progress,
    )

    # Cancelled after 2 symbols.
    assert report is not None
    assert report.skipped is True
    assert report.error == "Cancelled by user"
    assert report.items_count == 30
    assert calls == 2

    # Progress state reflects the partial run.
    assert progress["status"] == "cancelled"
    assert progress["items"] == 30
    assert progress["processed"] == 2
    assert progress["ok"] == 2


# ── Status / cancel manage endpoints ──────────────────────────────────


async def test_history_price_status_endpoint_reports_state():
    """The status endpoint serialises the shared in-memory state."""
    data = await sync_all_history_price_status()
    assert data.success is True
    assert data.data["status"] in ("idle", "running", "done", "cancelled", "error")


async def test_history_real_legal_status_endpoint_reports_state():
    data = await sync_all_history_real_legal_status()
    assert data.success is True
    assert data.data["status"] in ("idle", "running", "done", "cancelled", "error")


async def test_history_price_cancel_when_idle():
    """Cancelling with no running backfill is a clean no-op."""
    _HISTORY_PRICE_BACKFILL_STATE["status"] = "idle"
    _HISTORY_PRICE_BACKFILL_STATE["cancel_requested"] = False
    res = await cancel_sync_all_history_price()
    assert res.success is False
    assert res.data["cancelled"] is False


async def test_history_real_legal_cancel_when_idle():
    _HISTORY_REAL_LEGAL_BACKFILL_STATE["status"] = "idle"
    _HISTORY_REAL_LEGAL_BACKFILL_STATE["cancel_requested"] = False
    res = await cancel_sync_all_history_real_legal()
    assert res.success is False
    assert res.data["cancelled"] is False
