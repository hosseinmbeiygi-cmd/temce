"""Unit tests for the manual full-market candlestick backfill.

Covers the parameters added to ``_run_candlesticks_all`` so the manage
API can trigger a whole-market download from the UI:

1. ``max_symbols=0`` means "no limit" (whole market) instead of the env cap.
2. ``allow_weekend=True`` bypasses the Tehran weekend guard.
3. The ``progress`` dict receives live updates and can cancel the run.
4. The API-key masking / payload counting helpers behave correctly.
"""

from unittest.mock import AsyncMock

from apps.api.endpoints.brsapi import _count_payload, _mask_api_key
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
    """Build a fake session whose execute() answers snapshot/candlestick
    symbol queries."""
    have = have or set()

    class _Session:
        def __init__(self):
            self.commit = AsyncMock()

        async def execute(self, stmt):
            text = str(stmt)
            if "brsapi_candlesticks" in text:
                return _FakeResult([(s,) for s in sorted(have)])
            return _FakeResult([(s,) for s in symbols])

    return _Session()


def _make_service(ok=True, items=100):
    service = AsyncMock()
    service.sync_all_symbols = AsyncMock(return_value=SyncReport(
        endpoint="/Tsetmc/AllSymbols.php", success=True, items_count=10,
    ))
    service.sync_candlesticks = AsyncMock(return_value=SyncReport(
        endpoint="/Tsetmc/Candlestick.php", success=ok, items_count=items,
    ))
    return service


# ── Whole-market download (max_symbols=0) ─────────────────────────────


async def test_manual_backfill_max_symbols_zero_processes_all(monkeypatch):
    """max_symbols=0 (manual "download all symbols") is NOT capped by the
    settings default — every symbol in the market is processed."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod.brsapi_settings, "candle_daily_max_symbols", 1)
    monkeypatch.setattr(reg_mod.brsapi_settings, "candle_req_delay", 0)

    registry = BrsApiJobRegistry()
    session = _make_session(["فولاد", "فملی", "شپنا", "خودرو", "وبملت"])
    service = _make_service()

    report = await registry._run_candlesticks_all(
        session, service, max_symbols=0,
    )

    assert report is not None
    assert report.success is True
    # All 5 symbols x 3 types x 100 items
    assert report.items_count == 1500
    assert len(service.sync_candlesticks.call_args_list) == 15


async def test_manual_backfill_max_symbols_override(monkeypatch):
    """A positive max_symbols overrides the settings default for manual runs."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod.brsapi_settings, "candle_daily_max_symbols", 250)
    monkeypatch.setattr(reg_mod.brsapi_settings, "candle_req_delay", 0)

    registry = BrsApiJobRegistry()
    session = _make_session(["فولاد", "فملی", "شپنا"])
    service = _make_service()

    report = await registry._run_candlesticks_all(
        session, service, max_symbols=2,
    )

    assert report is not None
    assert report.items_count == 600          # 2 x 3 x 100
    assert len(service.sync_candlesticks.call_args_list) == 6


# ── Weekend override ──────────────────────────────────────────────────


async def test_manual_backfill_allow_weekend_bypasses_guard(monkeypatch):
    """Manual runs pass allow_weekend=True so an admin can always
    download data, even on a Tehran weekend."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod, "_is_tehran_weekend", lambda: True)
    monkeypatch.setattr(reg_mod.brsapi_settings, "candle_req_delay", 0)

    registry = BrsApiJobRegistry()
    session = _make_session(["فولاد", "فملی"])
    service = _make_service()

    report = await registry._run_candlesticks_all(
        session, service, allow_weekend=True,
    )

    assert report is not None
    assert report.skipped is not True
    assert report.items_count == 600          # 2 x 3 x 100
    service.sync_all_symbols.assert_awaited_once()


# ── Progress reporting + cancellation ────────────────────────────────


async def test_manual_backfill_reports_progress_and_cancels(monkeypatch):
    """The progress dict is updated live and setting cancel_requested
    stops the run after the current symbol."""
    import brsapi.jobs.registry as reg_mod

    monkeypatch.setattr(reg_mod.brsapi_settings, "candle_req_delay", 0)

    registry = BrsApiJobRegistry()
    # 4 symbols; cancel after the 2nd completes.
    symbols = ["فولاد", "فملی", "شپنا", "خودرو"]
    session = _make_session(symbols)
    service = _make_service()

    progress: dict = {}

    calls = 0

    async def _tracking_sync(session_, symbol, candle_type="3", count=None):
        nonlocal calls
        calls += 1
        # Cancel once two full symbols (6 requests) are done.
        if calls == 6:
            progress["cancel_requested"] = True
        return SyncReport(
            endpoint="/Tsetmc/Candlestick.php", success=True, items_count=100,
        )

    service.sync_candlesticks = _tracking_sync

    report = await registry._run_candlesticks_all(
        session, service, max_symbols=0, progress=progress,
    )

    # Cancelled after 2 symbols.
    assert report is not None
    assert report.skipped is True
    assert report.error == "Cancelled by user"
    assert report.items_count == 600
    # 2 full symbols x 3 types.
    assert calls == 6

    # Progress state reflects the partial run.
    assert progress["status"] == "cancelled"
    assert progress["items"] == 600
    assert progress["processed"] == 2
    assert progress["ok"] == 6


# ── API-key test helpers ─────────────────────────────────────────────


def test_mask_api_key():
    assert _mask_api_key("FreeSV0E1LSgB9RDjuf0QorSLViX8pPG") == "Free…8pPG"
    assert _mask_api_key("ABC123") == "A***3"
    assert _mask_api_key("AB") == "***"
    assert _mask_api_key("") == ""


def test_count_payload():
    assert _count_payload([1, 2, 3]) == 3
    assert _count_payload({"data": [1, 2, 3, 4]}) == 4
    assert _count_payload({"symbols": [1, 2]}) == 2
    assert _count_payload({"a": 1, "b": 2}) == 2
    assert _count_payload({}) == 0
    assert _count_payload(None) == 0
