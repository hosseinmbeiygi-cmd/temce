"""Unit tests for the manual full-market shareholder backfill.

Covers ``_run_shareholders_all`` so the manage API can trigger a
whole-market shareholder download from the UI (the same pattern already
exists for candlesticks):

1. ``max_symbols=0`` means "no limit" (whole market) instead of the cap.
2. ``allow_weekend=True`` bypasses the Tehran weekend guard.
3. The ``progress`` dict receives live updates and can cancel the run.
4. An empty AllSymbols response (holiday) skips the backfill entirely.
5. An AllSymbols API failure still processes from the existing symbol list.
6. The status / cancel manage endpoints behave correctly.
"""

from unittest.mock import AsyncMock

from apps.api.endpoints.brsapi import (
    _SHAREHOLDER_BACKFILL_STATE,
    cancel_sync_all_shareholders,
    sync_all_shareholders_status,
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


def _make_session(symbols, have=None):
    """Build a fake session whose execute() answers snapshot/shareholder
    symbol queries."""
    have = have or set()

    class _Session:
        def __init__(self):
            self.commit = AsyncMock()

        async def execute(self, stmt):
            text = str(stmt)
            if "brsapi_shareholder_records" in text:
                return _FakeResult([(s,) for s in sorted(have)])
            return _FakeResult([(s,) for s in symbols])

    return _Session()


def _make_service(ok=True, items=20, symbols_count=10):
    service = AsyncMock()
    service.sync_all_symbols = AsyncMock(return_value=SyncReport(
        endpoint="/Tsetmc/AllSymbols.php", success=True, items_count=symbols_count,
    ))
    service.sync_shareholders = AsyncMock(return_value=SyncReport(
        endpoint="/Tsetmc/Shareholder.php", success=ok, items_count=items,
    ))
    return service


# ── Whole-market download (max_symbols=0) ─────────────────────────────


async def test_shareholder_backfill_max_symbols_zero_processes_all(monkeypatch):
    """max_symbols=0 (manual "download all symbols") is NOT capped by the
    settings default — every symbol in the market is processed."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod.brsapi_settings, "shareholder_daily_max_symbols", 1)
    monkeypatch.setattr(reg_mod.brsapi_settings, "shareholder_req_delay", 0)

    registry = BrsApiJobRegistry()
    session = _make_session(["فولاد", "فملی", "شپنا", "خودرو", "وبملت"])
    service = _make_service()

    report = await registry._run_shareholders_all(
        session, service, max_symbols=0,
    )

    assert report is not None
    assert report.success is True
    # All 5 symbols x 20 records
    assert report.items_count == 100
    assert len(service.sync_shareholders.call_args_list) == 5


async def test_shareholder_backfill_max_symbols_override(monkeypatch):
    """A positive max_symbols overrides the settings default for manual runs."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod.brsapi_settings, "shareholder_daily_max_symbols", 1000)
    monkeypatch.setattr(reg_mod.brsapi_settings, "shareholder_req_delay", 0)

    registry = BrsApiJobRegistry()
    session = _make_session(["فولاد", "فملی", "شپنا"])
    service = _make_service()

    report = await registry._run_shareholders_all(
        session, service, max_symbols=2,
    )

    assert report is not None
    assert report.items_count == 40          # 2 x 20
    assert len(service.sync_shareholders.call_args_list) == 2


# ── Weekend override ──────────────────────────────────────────────────


async def test_shareholder_backfill_allow_weekend_bypasses_guard(monkeypatch):
    """Manual runs pass allow_weekend=True so an admin can always
    download data, even on a Tehran weekend."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod, "_is_tehran_weekend", lambda: True)
    monkeypatch.setattr(reg_mod.brsapi_settings, "shareholder_req_delay", 0)

    registry = BrsApiJobRegistry()
    session = _make_session(["فولاد", "فملی"])
    service = _make_service()

    report = await registry._run_shareholders_all(
        session, service, allow_weekend=True,
    )

    assert report is not None
    assert report.skipped is not True
    assert report.items_count == 40          # 2 x 20
    service.sync_all_symbols.assert_awaited_once()


# ── Empty-market guard (holiday) ──────────────────────────────────────


async def test_shareholder_backfill_skipped_on_empty_market(monkeypatch):
    """AllSymbols returning zero symbols (market closed/holiday) skips the
    whole shareholder backfill — no per-symbol requests are sent."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod.brsapi_settings, "shareholder_req_delay", 0)

    registry = BrsApiJobRegistry()
    session = _make_session(["فولاد", "فملی"])
    service = _make_service(symbols_count=0)   # market closed
    progress: dict = {}

    report = await registry._run_shareholders_all(session, service, progress=progress)

    assert report is not None
    assert report.skipped is True
    assert report.items_count == 0
    service.sync_shareholders.assert_not_called()
    # The worker surfaces a holiday-specific message (not the weekend one).
    assert "بازار بسته/تعطیل" in progress["message"]


async def test_shareholder_backfill_continues_on_symbols_api_error(monkeypatch):
    """An AllSymbols API failure (success=False) is NOT a holiday — the
    backfill proceeds using the existing symbol list."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod.brsapi_settings, "shareholder_req_delay", 0)

    registry = BrsApiJobRegistry()
    session = _make_session(["فولاد", "فملی"])
    service = _make_service()
    service.sync_all_symbols = AsyncMock(return_value=SyncReport(
        endpoint="/Tsetmc/AllSymbols.php", success=False, items_count=0, error="boom",
    ))

    report = await registry._run_shareholders_all(session, service)

    assert report is not None
    assert report.skipped is not True
    assert report.items_count == 40          # 2 x 20
    assert len(service.sync_shareholders.call_args_list) == 2


# ── Progress reporting + cancellation ────────────────────────────────


async def test_shareholder_backfill_reports_progress_and_cancels(monkeypatch):
    """The progress dict is updated live and setting cancel_requested
    stops the run after the current symbol."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod.brsapi_settings, "shareholder_req_delay", 0)

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
            endpoint="/Tsetmc/Shareholder.php", success=True, items_count=20,
        )

    service.sync_shareholders = _tracking_sync

    report = await registry._run_shareholders_all(
        session, service, max_symbols=0, progress=progress,
    )

    # Cancelled after 2 symbols.
    assert report is not None
    assert report.skipped is True
    assert report.error == "Cancelled by user"
    assert report.items_count == 40
    assert calls == 2

    # Progress state reflects the partial run.
    assert progress["status"] == "cancelled"
    assert progress["items"] == 40
    assert progress["processed"] == 2
    assert progress["ok"] == 2


# ── Status / cancel manage endpoints ──────────────────────────────────


async def test_shareholder_status_endpoint_reports_state():
    """The status endpoint serialises the shared in-memory state."""
    data = await sync_all_shareholders_status()
    assert data.success is True
    assert data.data["status"] in ("idle", "running", "done", "cancelled", "error")


async def test_shareholder_cancel_when_idle():
    """Cancelling with no running backfill is a clean no-op."""
    _SHAREHOLDER_BACKFILL_STATE["status"] = "idle"
    _SHAREHOLDER_BACKFILL_STATE["cancel_requested"] = False
    res = await cancel_sync_all_shareholders()
    assert res.success is False
    assert res.data["cancelled"] is False
