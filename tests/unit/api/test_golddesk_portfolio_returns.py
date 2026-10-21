"""ASGI contract for the GoldDesk portfolio returns surface.

Builds a minimal app from the real ``src.gold_desk.api`` router and stubs the DB
session, snapshot, holdings summary and the returns builder, so this asserts the
*wiring + response shape* of:

  * GET /gold/portfolio/returns  (new: nominal / real / USD block)
  * GET /gold/portfolio          (P&L path now carries the same block)
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.dependencies import get_db_session
from src.gold_desk import api as gold_api
from src.gold_desk.portfolio import PortfolioReturns


def _portfolio_returns() -> PortfolioReturns:
    return PortfolioReturns(
        nominal_pnl_irt=100.0,
        nominal_pnl_pct=100.0,
        nominal_xirr=1.0,
        real_xirr=0.0,
        usd_xirr=-0.05,
        cpi_basis="test-cpi",
        usd_basis="test-fx",
        unavailable={},
    )


def _summary() -> SimpleNamespace:
    return SimpleNamespace(total_cost=100.0, total_value=200.0, total_pnl=100.0, total_pnl_pct=100.0, holdings=[])


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(gold_api.router)
    app.dependency_overrides[get_db_session] = lambda: None

    stubs = {
        "get_hot_snapshot": AsyncMock(return_value={"snapshot_at": "2026-10-12T00:00:00"}),
        "get_holdings_grouped": AsyncMock(return_value=_summary()),
        "load_holdings_and_trades": AsyncMock(return_value=([], [])),
        "build_portfolio_returns": AsyncMock(return_value=_portfolio_returns()),
    }
    with pytest.MonkeyPatch.context() as mp:
        for name, mock in stubs.items():
            mp.setattr(gold_api, name, mock)
        yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def test_portfolio_returns_endpoint_shape(client: TestClient) -> None:
    r = client.get("/gold/portfolio/returns")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    returns = body["data"]["returns"]
    assert returns["nominal_pnl_irt"] == 100.0
    assert returns["nominal_xirr"] == 1.0
    assert returns["real_xirr"] == 0.0
    assert returns["usd_xirr"] == -0.05
    assert returns["cpi_basis"] == "test-cpi"
    assert returns["usd_basis"] == "test-fx"


def test_portfolio_endpoint_includes_returns_block(client: TestClient) -> None:
    r = client.get("/gold/portfolio")
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["total_pnl"] == 100.0
    assert body["data"]["returns"]["real_xirr"] == 0.0
    assert body["data"]["returns"]["usd_xirr"] == -0.05
