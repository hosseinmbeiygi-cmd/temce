from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.app import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_backtest_create(client: AsyncClient):
    payload = {
        "name": "E2E Test Backtest",
        "symbols": ["فولاد"],
        "strategy_type": "moving_average_crossover",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
    }
    response = await client.post("/api/v1/backtest/run", json=payload)
    assert response.status_code in (200, 201, 401, 422)


@pytest.mark.asyncio
async def test_backtest_list(client: AsyncClient):
    response = await client.get("/api/v1/backtest/runs")
    assert response.status_code in (200, 401)


@pytest.mark.asyncio
async def test_backtest_strategies(client: AsyncClient):
    response = await client.get("/api/v1/backtest/strategies")
    assert response.status_code in (200, 401)

