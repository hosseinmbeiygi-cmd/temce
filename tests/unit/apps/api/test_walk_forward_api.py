"""Layer 4 — API contract & integration for ``POST /api/v1/backtests/walk-forward``.

The route (``apps/api/endpoints/backtests.py``) is isolated from the DB by
overriding its ``get_backtest_service`` dependency with a fake that returns a
synthetic series and a deterministic simulator. Auth is provided by the shared
``user_client`` fixture (tests/unit/conftest.py).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient

from apps.api.dependencies import get_backtest_service
from backtesting.strategies.registry import register_all_strategies

_ENDPOINT = "/api/v1/backtests/walk-forward"
_N_BARS = 1200


@dataclass
class _EP:
    nav: float


@dataclass
class _Trade:
    pnl: float


@dataclass
class _Val:
    equity_curve: list
    trades: list


@dataclass
class _Run:
    success: bool
    value: Any


class _Simulator:
    def run(self, strategy: Any, *, initial_capital: float, data: list[dict[str, Any]]) -> _Run:
        n = max(len(data), 2)
        curve = [_EP(100.0 + 0.01 * i) for i in range(n)]
        return _Run(True, _Val(curve, [_Trade(1.0) for _ in range(max(n // 2, 1))]))


class _FakeBacktestService:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self._data = data
        self.simulator = _Simulator()

    async def _load_historical_data(self, symbol: str, start: Any, end: Any) -> list[dict[str, Any]]:
        return self._data


def _series(n: int = _N_BARS) -> list[dict[str, Any]]:
    register_all_strategies()
    start = datetime(2021, 1, 1, tzinfo=UTC)
    return [
        {
            "timestamp": start + timedelta(days=i),
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0 + i * 0.01,
            "prices": {"فولاد": 100.0 + i * 0.01},
            "instrument_id": "فولاد",
            "volume": 1000,
        }
        for i in range(n)
    ]


@pytest_asyncio.fixture
async def fake_service(app: FastAPI) -> AsyncGenerator[_FakeBacktestService, None]:
    service = _FakeBacktestService(_series())
    app.dependency_overrides[get_backtest_service] = lambda: service
    try:
        yield service
    finally:
        app.dependency_overrides.pop(get_backtest_service, None)


async def test_walk_forward_endpoint_returns_full_contract(
    user_client: AsyncClient, fake_service: _FakeBacktestService
) -> None:
    payload = {
        "symbol": "فولاد",
        "strategy": "moving_average_cross",
        "capital": 1_000_000_000,
        "windows": 4,
    }
    resp = await user_client.post(_ENDPOINT, json=payload)
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    for key in ("embargo_bars", "purged_bars", "deflated_sharpe", "is_sharpes", "oos_sharpes"):
        assert key in data, f"missing contract key: {key}"
    assert data["embargo_bars"] > 0
    assert data["purged_bars"] > 0
    assert len(data["is_sharpes"]) == len(data["oos_sharpes"]) == data["n_windows"]


async def test_walk_forward_backward_compatible_defaults(
    user_client: AsyncClient, fake_service: _FakeBacktestService
) -> None:
    """Omitting optional (non-model) purge/embargo fields must fall back to the
    optimizer defaults of 0.01, i.e. max(1, int(1200 * 0.01)) == 12 bars."""
    payload = {"symbol": "فولاد", "strategy": "moving_average_cross"}
    resp = await user_client.post(_ENDPOINT, json=payload)
    assert resp.status_code == 200, resp.text

    data = resp.json()["data"]
    expected_default = max(1, int(_N_BARS * 0.01))
    assert data["embargo_bars"] == expected_default
    assert data["purged_bars"] == expected_default
