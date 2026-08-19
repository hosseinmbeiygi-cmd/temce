"""Unit tests for the nightly symbol-detail full-market refresh.

Covers ``brsapi_symbol_details_all`` — the nightly 21:00 job that refreshes
the enriched ``brsapi_symbol_details`` table for the whole market (the
``/symbol-details`` frontend page reads from this table):

1. The job is registered with the nightly 15:00 cron and is enabled.
2. ``max_symbols=0`` means "no limit" (whole market) instead of the cap.
3. A positive ``max_symbols`` overrides the settings default.
4. Missing symbols (no detail row yet) are processed before already-synced ones.
5. ``allow_weekend=True`` bypasses the Tehran weekend guard.
6. An empty AllSymbols response (holiday) skips the refresh entirely.
7. An AllSymbols API failure still processes from the existing symbol list.
8. The ``progress`` dict receives live updates and can cancel the run.
9. ``run_job`` dispatches ``brsapi_symbol_details_all`` to the backfill.
"""

from unittest.mock import AsyncMock

from brsapi.jobs.registry import BRsAPI_SYNC_JOBS, BrsApiJobRegistry
from brsapi.services.sync_service import SyncReport


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)

    def __aiter__(self):
        return self._AsyncIter(self._rows)

    class _AsyncIter:
        def __init__(self, rows):
            self._it = iter(rows)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._it)
            except StopIteration:
                raise StopAsyncIteration

    def fetchall(self):
        return self._rows


def _make_session(symbols, have_detail=None):
    """Build a fake session whose execute() answers snapshot / detail symbol
    queries. ``brsapi_symbol_details`` answers have_detail (symbols already
    synced); everything else returns the full snapshot symbol list."""
    have_detail = have_detail or set()

    class _Session:
        def __init__(self):
            self.commit = AsyncMock()

        async def execute(self, stmt):
            text = str(stmt)
            if "brsapi_symbol_details" in text:
                return _FakeResult([(s,) for s in sorted(have_detail)])
            return _FakeResult([(s,) for s in symbols])

    return _Session()


def _make_service(ok=True, items=1, symbols_count=10):
    service = AsyncMock()
    service.sync_all_symbols = AsyncMock(return_value=SyncReport(
        endpoint="/Tsetmc/AllSymbols.php", success=True, items_count=symbols_count,
    ))
    service.sync_symbol_detail = AsyncMock(return_value=SyncReport(
        endpoint="/Tsetmc/Symbol.php", success=ok, items_count=items,
    ))
    return service


# ── Job registration ──────────────────────────────────────────────────


def test_symbol_details_job_registered_nightly():
    """brsapi_symbol_details_all is registered, enabled, and runs every night at 21:00."""
    job = next((j for j in BRsAPI_SYNC_JOBS if j.name == "brsapi_symbol_details_all"), None)
    assert job is not None, "brsapi_symbol_details_all missing from BRsAPI_SYNC_JOBS"
    assert job.enabled is True
    assert job.cron == "0 21 * * *"
    assert job.endpoint_config.path == "/Tsetmc/Symbol.php"


# ── Whole-market refresh (max_symbols=0) ──────────────────────────────


async def test_symbol_details_max_symbols_zero_processes_all(monkeypatch):
    """max_symbols=0 is NOT capped by the settings default — every symbol
    in the market is processed."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod.brsapi_settings, "symbol_detail_daily_max_symbols", 1)
    monkeypatch.setattr(reg_mod.brsapi_settings, "symbol_detail_req_delay", 0)

    registry = BrsApiJobRegistry()
    session = _make_session(["فولاد", "فملی", "شپنا", "خودرو", "وبملت"])
    service = _make_service()

    report = await registry._run_symbol_details_all(session, service, max_symbols=0)

    assert report is not None
    assert report.success is True
    assert report.items_count == 5           # 5 symbols x 1 record
    assert len(service.sync_symbol_detail.call_args_list) == 5


async def test_symbol_details_max_symbols_override(monkeypatch):
    """A positive max_symbols overrides the settings default."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod.brsapi_settings, "symbol_detail_daily_max_symbols", 1000)
    monkeypatch.setattr(reg_mod.brsapi_settings, "symbol_detail_req_delay", 0)

    registry = BrsApiJobRegistry()
    session = _make_session(["فولاد", "فملی", "شپنا"])
    service = _make_service()

    report = await registry._run_symbol_details_all(session, service, max_symbols=2)

    assert report is not None
    assert report.items_count == 2           # 2 x 1
    assert len(service.sync_symbol_detail.call_args_list) == 2


# ── Missing-first ordering ────────────────────────────────────────────


async def test_symbol_details_missing_symbols_processed_first(monkeypatch):
    """Symbols without any detail row are processed before already-synced ones."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod.brsapi_settings, "symbol_detail_req_delay", 0)

    registry = BrsApiJobRegistry()
    symbols = ["فولاد", "فملی", "شپنا"]
    session = _make_session(symbols, have_detail={"فملی", "شپنا"})  # فولاد missing
    service = _make_service()

    report = await registry._run_symbol_details_all(session, service, max_symbols=0)

    assert report is not None
    assert report.items_count == 3           # 3 x 1
    called = [c.args[1] for c in service.sync_symbol_detail.call_args_list]
    assert called == ["فولاد", "فملی", "شپنا"]  # missing first


# ── Weekend override ──────────────────────────────────────────────────


async def test_symbol_details_allow_weekend_bypasses_guard(monkeypatch):
    """Manual runs pass allow_weekend=True so an admin can always refresh
    details, even on a Tehran weekend."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod, "_is_tehran_weekend", lambda: True)
    monkeypatch.setattr(reg_mod.brsapi_settings, "symbol_detail_req_delay", 0)

    registry = BrsApiJobRegistry()
    session = _make_session(["فولاد", "فملی"])
    service = _make_service()

    report = await registry._run_symbol_details_all(session, service, allow_weekend=True)

    assert report is not None
    assert report.skipped is not True
    assert report.items_count == 2           # 2 x 1
    service.sync_all_symbols.assert_awaited_once()


async def test_symbol_details_skipped_on_weekend(monkeypatch):
    """On a Tehran weekend (without allow_weekend) the refresh is skipped."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod, "_is_tehran_weekend", lambda: True)

    registry = BrsApiJobRegistry()
    session = _make_session(["فولاد", "فملی"])
    service = _make_service()

    report = await registry._run_symbol_details_all(session, service)

    assert report is not None
    assert report.skipped is True
    assert report.items_count == 0
    service.sync_symbol_detail.assert_not_called()


# ── Empty-market guard (holiday) ──────────────────────────────────────


async def test_symbol_details_skipped_on_empty_market(monkeypatch):
    """AllSymbols returning zero symbols (market closed/holiday) skips the
    whole refresh — no per-symbol requests are sent."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod.brsapi_settings, "symbol_detail_req_delay", 0)

    registry = BrsApiJobRegistry()
    session = _make_session(["فولاد", "فملی"])
    service = _make_service(symbols_count=0)   # market closed
    progress: dict = {}

    report = await registry._run_symbol_details_all(session, service, progress=progress)

    assert report is not None
    assert report.skipped is True
    assert report.items_count == 0
    service.sync_symbol_detail.assert_not_called()
    # The worker surfaces a holiday-specific message (not the weekend one).
    assert "بازار بسته/تعطیل" in progress["message"]


async def test_symbol_details_continues_on_symbols_api_error(monkeypatch):
    """An AllSymbols API failure (success=False) is NOT a holiday — the
    refresh proceeds using the existing symbol list."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod.brsapi_settings, "symbol_detail_req_delay", 0)

    registry = BrsApiJobRegistry()
    session = _make_session(["فولاد", "فملی"])
    service = _make_service()
    service.sync_all_symbols = AsyncMock(return_value=SyncReport(
        endpoint="/Tsetmc/AllSymbols.php", success=False, items_count=0, error="boom",
    ))

    report = await registry._run_symbol_details_all(session, service)

    assert report is not None
    assert report.skipped is not True
    assert report.items_count == 2           # 2 x 1
    assert len(service.sync_symbol_detail.call_args_list) == 2


# ── Progress reporting + cancellation ────────────────────────────────


async def test_symbol_details_reports_progress_and_cancels(monkeypatch):
    """The progress dict is updated live and setting cancel_requested
    stops the run after the current symbol."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod.brsapi_settings, "symbol_detail_req_delay", 0)

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
            endpoint="/Tsetmc/Symbol.php", success=True, items_count=1,
        )

    service.sync_symbol_detail = _tracking_sync

    report = await registry._run_symbol_details_all(
        session, service, max_symbols=0, progress=progress,
    )

    # Cancelled after 2 symbols.
    assert report is not None
    assert report.skipped is True
    assert report.error == "Cancelled by user"
    assert report.items_count == 2
    assert calls == 2

    # Progress state reflects the partial run.
    assert progress["status"] == "cancelled"
    assert progress["items"] == 2
    assert progress["processed"] == 2
    assert progress["ok"] == 2


# ── run_job dispatch ──────────────────────────────────────────────────


async def test_run_job_dispatches_symbol_details_all(monkeypatch):
    """run_job('brsapi_symbol_details_all') routes to _run_symbol_details_all."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod.brsapi_settings, "symbol_detail_req_delay", 0)

    registry = BrsApiJobRegistry()
    registry.register_many(BRsAPI_SYNC_JOBS)

    session = _make_session(["فولاد", "فملی"])

    # Stub the two async pieces run_job uses before dispatch.
    monkeypatch.setattr(reg_mod, "get_session", lambda: _FakeResult([session]))
    monkeypatch.setattr(reg_mod, "get_client", AsyncMock())

    called = {}

    async def _fake_backfill(sess, svc, **_kwargs):
        called["sess"] = sess
        called["svc"] = svc
        return SyncReport(endpoint="/Tsetmc/Symbol.php", success=True, items_count=2)

    registry._run_symbol_details_all = _fake_backfill

    report = await registry.run_job("brsapi_symbol_details_all")

    assert report is not None
    assert report.success is True
    # run_job built its own BrsApiSyncService and passed it with our session.
    assert called.get("sess") is session
    assert called.get("svc") is not None
