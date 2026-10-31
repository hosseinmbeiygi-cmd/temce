"""Dispatcher bridge for jobs registered in the BrsApi job registry.

The queue carries names published by the scheduler (``brsapi_all_symbols``,
``gold_snapshot``, ...). ``BrsApiJobRegistry.run_job`` is the only entry point
that applies the market-hours gate and routes both endpoint and direct jobs,
so the dispatcher must delegate to it instead of a hard-coded GoldDesk list.
"""

from __future__ import annotations

import pytest

from brsapi.services.sync_service import SyncReport
from jobs.job_dispatcher import JobDispatcher
from jobs.job_registry import JobRegistry


class FakeBrsApiRegistry:
    def __init__(self, report: SyncReport | None) -> None:
        self._report = report
        self.calls: list[str] = []

    def get(self, name: str) -> object | None:
        if name.startswith("brsapi_") or name == "gold_snapshot":
            return object()
        return None

    async def run_job(self, name: str, *, force: bool = False) -> SyncReport | None:
        self.calls.append(name)
        return self._report


@pytest.fixture
def dispatcher() -> JobDispatcher:
    return JobDispatcher(registry=JobRegistry())


@pytest.mark.asyncio
async def test_dispatch_runs_registered_brsapi_job(monkeypatch, dispatcher):
    fake = FakeBrsApiRegistry(
        SyncReport(endpoint="brsapi_all_symbols", success=True, items_count=3, duration_ms=1.0)
    )
    monkeypatch.setattr("brsapi.jobs.registry.get_brsapi_job_registry", lambda: fake)

    result = await dispatcher.dispatch("brsapi_all_symbols")

    assert fake.calls == ["brsapi_all_symbols"]
    assert result.success is True
    assert result.skipped is False


@pytest.mark.asyncio
async def test_dispatch_reports_market_hours_skip(monkeypatch, dispatcher):
    """``run_job`` returns ``None`` when the market-hours gate is closed."""
    fake = FakeBrsApiRegistry(None)
    monkeypatch.setattr("brsapi.jobs.registry.get_brsapi_job_registry", lambda: fake)

    result = await dispatcher.dispatch("brsapi_all_symbols")

    assert result.success is False
    assert result.skipped is True
    assert "skip" in result.message.lower()


@pytest.mark.asyncio
async def test_dispatch_unknown_job_is_still_not_found(monkeypatch, dispatcher):
    fake = FakeBrsApiRegistry(None)
    monkeypatch.setattr("brsapi.jobs.registry.get_brsapi_job_registry", lambda: fake)

    result = await dispatcher.dispatch("definitely_not_a_job")

    assert result.success is False
    assert result.skipped is False
    assert "not found" in result.error.lower()
    assert fake.calls == []
