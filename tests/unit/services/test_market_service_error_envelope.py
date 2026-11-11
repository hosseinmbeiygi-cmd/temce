"""A source failure must not be serialized as ``success=True`` with an empty list.

Audit API-02. ``MarketService`` swallowed every source exception and returned
``Result.ok([])`` / ``Result.ok({})``, so the endpoint answered
``{"success": true, "data": []}`` and the UI rendered "no data" instead of
"the source failed" — exactly the ambiguity ``api-envelope.ts`` exists to stop.

Rules locked here:
  * all sources errored and nothing was returned  → ``success is False``,
  * sources answered cleanly with nothing        → ``success is True, []``,
  * any source answered with data                → ``success is True``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.result import Result
from services.market_service import MarketService


class _Brsapi:
    def __init__(self, *, exc: Exception | None = None, data=None, snapshot=None) -> None:
        self.exc = exc
        self.data = data if data is not None else []
        self.snapshot = snapshot

    async def get_latest_indices(self):
        if self.exc:
            raise self.exc
        return self.data

    async def get_latest_snapshots(self, limit: int = 500):
        if self.exc:
            raise self.exc
        return self.data

    async def get_historical_daily(self, symbol: str, limit: int = 500):
        if self.exc:
            raise self.exc
        return self.data

    async def get_symbol_snapshot(self, symbol: str):
        if self.exc:
            raise self.exc
        return self.snapshot


class _Client:
    def __init__(self, *, exc: Exception | None = None, result=None) -> None:
        self.exc = exc
        self.result = result if result is not None else Result.ok(SimpleNamespace(data=None))

    async def fetch(self, endpoint, params=None):
        if self.exc:
            raise self.exc
        return self.result


class _InstrumentRepo:
    def __init__(self, *, exc: Exception | None = None, entity=None) -> None:
        self.exc = exc
        self.entity = entity

    async def get_by_symbol(self, symbol: str):
        if self.exc:
            raise self.exc
        return Result.ok(self.entity)


class _QuoteRepo:
    def __init__(self, *, exc: Exception | None = None, rows=None) -> None:
        self.exc = exc
        self.rows = rows or []

    async def get_range(self, *_args, **_kwargs):
        if self.exc:
            raise self.exc
        return Result.ok(self.rows)


def _service(**kwargs) -> MarketService:
    kwargs.setdefault("quote_repo", _QuoteRepo())
    kwargs.setdefault("instrument_repo", _InstrumentRepo())
    return MarketService(**kwargs)


# ── get_index_values ────────────────────────────────────────────────────────


async def test_index_values_fails_when_both_sources_error() -> None:
    svc = _service(
        brsapi_query_service=_Brsapi(exc=RuntimeError("db down")),
        brsapi_client=_Client(exc=RuntimeError("api down")),
    )

    result = await svc.get_index_values()

    assert result.success is False
    assert result.error


async def test_index_values_fails_when_the_live_fetch_is_rejected() -> None:
    svc = _service(
        brsapi_query_service=_Brsapi(),  # clean, empty
        brsapi_client=_Client(result=Result.fail("provider blocked")),
    )

    result = await svc.get_index_values()

    assert result.success is False


async def test_index_values_returns_empty_success_when_sources_are_clean() -> None:
    svc = _service(
        brsapi_query_service=_Brsapi(),  # clean, empty
        brsapi_client=_Client(),  # clean, empty payload
    )

    result = await svc.get_index_values()

    assert result.success is True
    assert result.value == []


# ── get_sector_summary ──────────────────────────────────────────────────────


async def test_sector_summary_fails_when_sources_error() -> None:
    svc = _service(
        brsapi_query_service=_Brsapi(exc=RuntimeError("db down")),
        brsapi_client=_Client(exc=RuntimeError("api down")),
    )

    result = await svc.get_sector_summary()

    assert result.success is False


async def test_sector_summary_fails_when_the_live_fetch_is_rejected() -> None:
    svc = _service(
        brsapi_query_service=_Brsapi(),  # clean, empty
        brsapi_client=_Client(result=Result.fail("provider blocked")),
    )

    result = await svc.get_sector_summary()

    assert result.success is False


# ── get_ohlcv / get_historical_quotes ───────────────────────────────────────


async def test_ohlcv_fails_when_every_source_errors() -> None:
    svc = _service(
        brsapi_query_service=_Brsapi(exc=RuntimeError("db down"), snapshot={"l18": "123"}),
        brsapi_client=_Client(result=Result.fail("api down")),
        instrument_repo=_InstrumentRepo(exc=RuntimeError("quotes db down")),
    )

    result = await svc.get_ohlcv("AAA", "2026-10-01", "2026-10-29")

    assert result.success is False


async def test_ohlcv_returns_empty_success_when_no_source_errors() -> None:
    svc = _service(
        brsapi_query_service=_Brsapi(),  # clean, empty
        brsapi_client=_Client(),  # clean, empty payload
        instrument_repo=_InstrumentRepo(),  # symbol not found → clean empty
    )

    result = await svc.get_ohlcv("AAA", "2026-10-01", "2026-10-29")

    assert result.success is True
    assert result.value == []


async def test_historical_quotes_fails_when_the_quotes_table_errors() -> None:
    svc = _service(
        brsapi_query_service=_Brsapi(exc=RuntimeError("brsapi db down")),
        brsapi_client=_Client(result=Result.fail("api down")),
        instrument_repo=_InstrumentRepo(exc=RuntimeError("quotes db down")),
    )

    result = await svc.get_historical_quotes("AAA", "2026-10-01", "2026-10-29")

    assert result.success is False


# ── get_batch_sparklines ────────────────────────────────────────────────────


async def test_batch_sparklines_fails_on_db_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _broken_session():
        async def _gen():
            raise RuntimeError("db down")
            yield  # pragma: no cover — makes this an async generator

        return _gen()

    monkeypatch.setattr("core.database.get_session", _broken_session)

    result = await _service().get_batch_sparklines(["AAA"])

    assert result.success is False
