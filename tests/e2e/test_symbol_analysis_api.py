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
async def test_symbol_info(client: AsyncClient):
    response = await client.get("/api/v1/symbols/فولاد")
    assert response.status_code in (200, 401, 404)


@pytest.mark.asyncio
async def test_symbol_quotes(client: AsyncClient):
    response = await client.get("/api/v1/symbols/فولاد/quotes")
    assert response.status_code in (200, 401, 404)


@pytest.mark.asyncio
async def test_symbol_ohlcv(client: AsyncClient):
    response = await client.get("/api/v1/symbols/فولاد/ohlcv")
    assert response.status_code in (200, 401, 404)


@pytest.mark.asyncio
async def test_symbol_indicators(client: AsyncClient):
    response = await client.get("/api/v1/symbols/فولاد/indicators")
    assert response.status_code in (200, 401, 404)


@pytest.mark.asyncio
async def test_symbol_news(client: AsyncClient):
    response = await client.get("/api/v1/symbols/فولاد/news")
    assert response.status_code in (200, 401, 404)


@pytest.mark.asyncio
async def test_symbol_analytics(client: AsyncClient):
    response = await client.get("/api/v1/symbols/فولاد/analytics")
    assert response.status_code in (200, 401, 404)


@pytest.mark.asyncio
async def test_instruments_list(client: AsyncClient):
    response = await client.get("/api/v1/instruments")
    assert response.status_code in (200, 401)


@pytest.mark.asyncio
async def test_instruments_search(client: AsyncClient):
    response = await client.get("/api/v1/instruments/search?q=فولاد")
    assert response.status_code in (200, 401)

