from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.app import app


@pytest.fixture
async def client():
    from core.database import close_database, init_database

    await close_database()
    await init_database()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_market_overview(client: AsyncClient):
    response = await client.get("/api/v1/market/overview")
    assert response.status_code in (200, 401)


@pytest.mark.asyncio
async def test_market_gainers(client: AsyncClient):
    response = await client.get("/api/v1/market/gainers")
    assert response.status_code in (200, 401)


@pytest.mark.asyncio
async def test_market_losers(client: AsyncClient):
    response = await client.get("/api/v1/market/losers")
    assert response.status_code in (200, 401)


@pytest.mark.asyncio
async def test_market_active(client: AsyncClient):
    response = await client.get("/api/v1/market/active")
    assert response.status_code in (200, 401)
