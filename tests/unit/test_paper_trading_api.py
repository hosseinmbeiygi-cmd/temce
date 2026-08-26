"""Unit tests for the Paper Trading API endpoints (``apps/api/endpoints/paper_trading.py``).

Covers all 7 routes:
  GET  /paper-trading/dashboard
  GET  /paper-trading/equity
  GET  /paper-trading/trades
  POST /paper-trading/trades
  POST /paper-trading/trades/{id}/close
  POST /paper-trading/auto-close
  GET  /paper-trading/signals

Each test runs a minimal FastAPI app with the ``_svc`` dependency overridden
by an ``AsyncMock(spec=PaperTradingService)`` — no database needed.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from apps.api.endpoints.paper_trading import _svc
from apps.api.endpoints.paper_trading import router as paper_trading_router
from core.typing import PaginatedResult, Result
from services.paper_trading_service import PaperTradingService

pytestmark = pytest.mark.asyncio


def make_app(svc: Any = None) -> FastAPI:
    app = FastAPI()
    app.include_router(paper_trading_router, prefix="/paper-trading")
    if svc is not None:
        app.dependency_overrides[_svc] = lambda: svc
    return app


@pytest.fixture
def svc() -> AsyncMock:
    return AsyncMock(spec=PaperTradingService)


async def _get(app: FastAPI, path: str) -> Any:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


async def _post(app: FastAPI, path: str, json: dict[str, Any] | None = None) -> Any:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(path, json=json)


def _paginated(items: list[Any], total: int = 1, page: int = 1, page_size: int = 50) -> PaginatedResult:
    total_pages = max((total + page_size - 1) // page_size, 1)
    return PaginatedResult(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)


# ═══════════════════════════════════════════════════════════════
#  GET /dashboard
# ═══════════════════════════════════════════════════════════════


class TestDashboard:
    async def test_success(self, svc: AsyncMock) -> None:
        svc.get_dashboard = AsyncMock(return_value={"total_pnl": 5000.0, "win_rate": 60.0})
        resp = await _get(make_app(svc), "/paper-trading/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["total_pnl"] == 5000.0
        assert data["data"]["win_rate"] == 60.0

    async def test_service_error(self, svc: AsyncMock) -> None:
        svc.get_dashboard = AsyncMock(side_effect=RuntimeError("db down"))
        resp = await _get(make_app(svc), "/paper-trading/dashboard")
        data = resp.json()
        assert data["success"] is False
        assert "db down" in data["error"]["message"]


# ═══════════════════════════════════════════════════════════════
#  GET /equity
# ═══════════════════════════════════════════════════════════════


class TestEquity:
    async def test_success(self, svc: AsyncMock) -> None:
        svc.get_equity_history = AsyncMock(return_value=[{"date": "1404-01-01", "equity": 1e9}])
        resp = await _get(make_app(svc), "/paper-trading/equity")
        data = resp.json()
        assert data["success"] is True
        assert len(data["data"]) == 1

    async def test_passes_limit(self, svc: AsyncMock) -> None:
        svc.get_equity_history = AsyncMock(return_value=[])
        await _get(make_app(svc), "/paper-trading/equity?limit=30")
        svc.get_equity_history.assert_awaited_once_with(limit=30)

    async def test_limit_validation(self, svc: AsyncMock) -> None:
        assert (await _get(make_app(svc), "/paper-trading/equity?limit=0")).status_code == 422
        assert (await _get(make_app(svc), "/paper-trading/equity?limit=999")).status_code == 422

    async def test_service_error_returns_empty_list(self, svc: AsyncMock) -> None:
        svc.get_equity_history = AsyncMock(side_effect=RuntimeError("boom"))
        resp = await _get(make_app(svc), "/paper-trading/equity")
        data = resp.json()
        assert data["success"] is False
        assert data["data"] == []


# ═══════════════════════════════════════════════════════════════
#  GET /trades
# ═══════════════════════════════════════════════════════════════


class TestListTrades:
    async def test_success(self, svc: AsyncMock) -> None:
        svc.list_trades = AsyncMock(return_value=Result.ok(_paginated([{"id": "t1", "symbol": "فولاد"}])))
        resp = await _get(make_app(svc), "/paper-trading/trades")
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["total"] == 1
        assert data["data"]["items"][0]["symbol"] == "فولاد"

    async def test_query_params_passed(self, svc: AsyncMock) -> None:
        svc.list_trades = AsyncMock(return_value=Result.ok(_paginated([])))
        await _get(make_app(svc), "/paper-trading/trades?status=open&symbol=خودرو&page=2&page_size=10")
        svc.list_trades.assert_awaited_once_with(status="open", symbol="خودرو", page=2, page_size=10)

    async def test_failure_result(self, svc: AsyncMock) -> None:
        svc.list_trades = AsyncMock(return_value=Result.fail("no trades"))
        resp = await _get(make_app(svc), "/paper-trading/trades")
        data = resp.json()
        assert data["success"] is False
        assert data["data"] is None

    async def test_exception_returns_empty_pagination(self, svc: AsyncMock) -> None:
        svc.list_trades = AsyncMock(side_effect=RuntimeError("boom"))
        resp = await _get(make_app(svc), "/paper-trading/trades")
        data = resp.json()
        assert data["success"] is False
        assert data["data"]["items"] == []
        assert data["data"]["total"] == 0


# ═══════════════════════════════════════════════════════════════
#  POST /trades
# ═══════════════════════════════════════════════════════════════


class TestOpenTrade:
    async def test_success(self, svc: AsyncMock) -> None:
        svc.open_trade = AsyncMock(return_value=Result.ok({"trade_id": "t1"}))
        resp = await _post(
            make_app(svc),
            "/paper-trading/trades",
            json={"snapshot_id": "s1", "quantity": 100, "capital_allocated": 5_000_000, "entry_price": 4500},
        )
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["trade_id"] == "t1"
        svc.open_trade.assert_awaited_once_with(
            snapshot_id="s1", quantity=100.0, capital_allocated=5_000_000.0,
            entry_price=4500.0, entry_notes=None,
        )

    async def test_without_entry_price(self, svc: AsyncMock) -> None:
        svc.open_trade = AsyncMock(return_value=Result.ok({"trade_id": "t2"}))
        resp = await _post(
            make_app(svc),
            "/paper-trading/trades",
            json={"snapshot_id": "s2", "quantity": 10},
        )
        assert resp.json()["success"] is True
        svc.open_trade.assert_awaited_once_with(
            snapshot_id="s2", quantity=10.0, capital_allocated=0.0,
            entry_price=None, entry_notes=None,
        )

    async def test_failure_result(self, svc: AsyncMock) -> None:
        svc.open_trade = AsyncMock(return_value=Result.fail("snapshot not found"))
        resp = await _post(make_app(svc), "/paper-trading/trades", json={"snapshot_id": "missing"})
        data = resp.json()
        assert data["success"] is False
        assert "snapshot not found" in data["error"]["message"]

    async def test_exception(self, svc: AsyncMock) -> None:
        svc.open_trade = AsyncMock(side_effect=ValueError("bad body"))
        resp = await _post(make_app(svc), "/paper-trading/trades", json={"snapshot_id": "s1"})
        data = resp.json()
        assert data["success"] is False
        assert "bad body" in data["error"]["message"]


# ═══════════════════════════════════════════════════════════════
#  POST /trades/{id}/close
# ═══════════════════════════════════════════════════════════════


class TestCloseTrade:
    async def test_success(self, svc: AsyncMock) -> None:
        svc.close_trade = AsyncMock(return_value=Result.ok({"pnl": 1500.0}))
        resp = await _post(
            make_app(svc),
            "/paper-trading/trades/t1/close",
            json={"exit_price": 4800, "exit_reason": "target", "exit_notes": "هدف رسید"},
        )
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["pnl"] == 1500.0
        svc.close_trade.assert_awaited_once_with(
            trade_id="t1", exit_price=4800.0, exit_reason="target", exit_notes="هدف رسید",
        )

    async def test_default_body_uses_manual_reason(self, svc: AsyncMock) -> None:
        svc.close_trade = AsyncMock(return_value=Result.ok({"pnl": 0.0}))
        resp = await _post(make_app(svc), "/paper-trading/trades/t1/close", json={})
        assert resp.json()["success"] is True
        svc.close_trade.assert_awaited_once_with(
            trade_id="t1", exit_price=None, exit_reason="manual", exit_notes=None,
        )

    async def test_failure_result(self, svc: AsyncMock) -> None:
        svc.close_trade = AsyncMock(return_value=Result.fail("trade not found"))
        resp = await _post(make_app(svc), "/paper-trading/trades/nope/close", json={})
        data = resp.json()
        assert data["success"] is False
        assert "trade not found" in data["error"]["message"]


# ═══════════════════════════════════════════════════════════════
#  POST /auto-close
# ═══════════════════════════════════════════════════════════════


class TestAutoClose:
    async def test_success(self, svc: AsyncMock) -> None:
        svc.auto_close_due_trades = AsyncMock(return_value=Result.ok(2))
        resp = await _post(make_app(svc), "/paper-trading/auto-close")
        data = resp.json()
        assert data["success"] is True
        assert data["data"] == {"closed": 2}

    async def test_exception(self, svc: AsyncMock) -> None:
        svc.auto_close_due_trades = AsyncMock(side_effect=RuntimeError("boom"))
        resp = await _post(make_app(svc), "/paper-trading/auto-close")
        data = resp.json()
        assert data["success"] is False
        assert "boom" in data["error"]["message"]


# ═══════════════════════════════════════════════════════════════
#  GET /signals
# ═══════════════════════════════════════════════════════════════


class TestSignals:
    async def test_success(self, svc: AsyncMock) -> None:
        svc.list_snapshots = AsyncMock(return_value=Result.ok(_paginated([{"symbol": "فولاد", "direction": "buy"}])))
        resp = await _get(make_app(svc), "/paper-trading/signals")
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["items"][0]["direction"] == "buy"

    async def test_query_params_passed(self, svc: AsyncMock) -> None:
        svc.list_snapshots = AsyncMock(return_value=Result.ok(_paginated([])))
        await _get(make_app(svc), "/paper-trading/signals?symbol=شپنا&market=tse&direction=buy&page=3&page_size=25")
        svc.list_snapshots.assert_awaited_once_with(
            page=3, page_size=25, symbol="شپنا", market="tse", direction="buy",
        )

    async def test_exception_returns_empty_pagination(self, svc: AsyncMock) -> None:
        svc.list_snapshots = AsyncMock(side_effect=RuntimeError("boom"))
        resp = await _get(make_app(svc), "/paper-trading/signals")
        data = resp.json()
        assert data["success"] is False
        assert data["data"]["items"] == []
        assert data["data"]["total"] == 0
