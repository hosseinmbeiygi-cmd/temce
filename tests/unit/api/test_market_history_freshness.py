"""The three daily-history endpoints must publish a source timestamp (API-04/FE).

``/market/flow-history``, ``/market/value-history`` and
``/market/ownership-history`` serve rows whose ``date`` is the Jalali market
day — not an instant. The only honest source timestamp is ``created_at`` (when
the platform stored the row); publishing it lets ``LiveDataBanner`` tell a
fresh sync from a stale table instead of leaving freshness unknown forever.

Offline: a fake session replays the exact result shapes the routes consume.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any

from apps.api.endpoints import market as market_ep

DAY_1 = datetime(2026, 10, 28, 8, 15, 0)
DAY_2 = datetime(2026, 10, 29, 9, 30, 0)
DAY_2_ISO = "2026-10-29T09:30:00"


class _Result:
    def __init__(self, rows: list[Any] | None = None, scalar: Any = None) -> None:
        self._rows = list(rows or [])
        self._scalar = scalar

    def scalars(self) -> _Result:
        return self

    def all(self) -> list[Any]:
        return list(self._rows)

    def scalar_one_or_none(self) -> Any:
        return self._scalar


class _Session:
    def __init__(self, *results: _Result) -> None:
        self._queue = list(results)
        self.calls = 0

    async def execute(self, statement: Any, params: Any = None) -> _Result:
        self.calls += 1
        return self._queue.pop(0) if self._queue else _Result()


def _brsapi(*results: _Result) -> SimpleNamespace:
    return SimpleNamespace(session=_Session(*results))


# ── /market/flow-history ───────────────────────────────────────────────────


async def test_flow_history_publishes_the_newest_write_time() -> None:
    rows = [
        SimpleNamespace(
            symbol="فولاد",
            buy_real_value=3e9,
            sell_real_value=1e9,
            buy_legal_value=1e9,
            sell_legal_value=0.5e9,
            created_at=DAY_1,
        ),
        SimpleNamespace(
            symbol="خودرو",
            buy_real_value=2e9,
            sell_real_value=1e9,
            buy_legal_value=0.0,
            sell_legal_value=1e9,
            created_at=DAY_2,
        ),
    ]
    brsapi = _brsapi(_Result(scalar="1405-06-23"), _Result(rows=rows))

    resp = await market_ep.market_flow_history(limit=8, brsapi=brsapi)

    assert resp.success is True
    assert resp.data_as_of == DAY_2_ISO
    assert [row["symbol"] for row in resp.data] == ["فولاد", "خودرو"]


async def test_flow_history_empty_table_has_no_timestamp() -> None:
    brsapi = _brsapi(_Result(scalar=None))

    resp = await market_ep.market_flow_history(limit=8, brsapi=brsapi)

    assert resp.success is True
    assert resp.data == []
    assert resp.data_as_of is None


# ── /market/value-history ──────────────────────────────────────────────────


async def test_value_history_publishes_the_newest_write_time() -> None:
    groups = [
        SimpleNamespace(date="1405-06-22", total_value=1e13, created_at=DAY_1),
        SimpleNamespace(date="1405-06-23", total_value=1.2e13, created_at=DAY_2),
    ]
    brsapi = _brsapi(_Result(rows=["1405-06-23", "1405-06-22"]), _Result(rows=groups))

    resp = await market_ep.market_value_history(days=5, brsapi=brsapi)

    assert resp.success is True
    assert resp.data_as_of == DAY_2_ISO
    assert resp.data[-1]["value_b"] == 12000.0


# ── /market/ownership-history ──────────────────────────────────────────────


async def test_ownership_history_publishes_the_newest_write_time() -> None:
    groups = [
        SimpleNamespace(
            date="1405-06-23",
            real_buy=5e9,
            real_sell=4e9,
            legal_buy=2e9,
            legal_sell=1e9,
            created_at=DAY_2,
        ),
    ]
    brsapi = _brsapi(_Result(rows=["1405-06-23"]), _Result(rows=groups))

    resp = await market_ep.market_ownership_history(days=5, brsapi=brsapi)

    assert resp.success is True
    assert resp.data_as_of == DAY_2_ISO
    assert resp.data[0]["real_b"] == 1.0
