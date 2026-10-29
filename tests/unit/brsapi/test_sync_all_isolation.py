"""One failing provider must not abort the other sync categories.

Audit DS-07. ``sync_all`` awaited every operation without a guard, so a DB or
session error in ``TSETMC Symbols`` skipped Index/IME/Gold/Crypto entirely.
"""

from __future__ import annotations

import pytest

import brsapi.services.sync_service as sync_module
from brsapi.services.sync_service import BrsApiSyncService, SyncReport


@pytest.fixture
def fast_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sync_module, "SYNC_ALL_INTER_OP_DELAY_SECONDS", 0.0)


async def test_a_failing_operation_is_recorded_and_the_rest_still_run(
    fast_sync: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = BrsApiSyncService()
    calls: list[str] = []

    async def _boom(*_args, **_kwargs):
        calls.append("boom")
        raise RuntimeError("db down")

    async def _ok(*_args, **_kwargs):
        calls.append("ok")
        return SyncReport(endpoint="ok", success=True)

    for method in (
        "sync_index",
        "sync_options",
        "sync_ime_futures",
        "sync_ime_options",
        "sync_ime_certificates",
        "sync_ime_funds",
        "sync_commodities",
        "sync_crypto",
        "sync_gold_currency",
    ):
        monkeypatch.setattr(service, method, _ok)
    monkeypatch.setattr(service, "sync_all_symbols", _boom)

    reports = await service.sync_all(session=object())  # type: ignore[arg-type]

    assert len(calls) == 11, "every operation must be attempted"
    assert len(reports) == 11
    assert reports[0].success is False
    assert "db down" in (reports[0].error or "")
    assert reports[0].outcome == "source_error"
    assert all(report.success for report in reports[1:])
