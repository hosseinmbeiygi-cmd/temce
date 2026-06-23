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
async def test_market_summary(client: AsyncClient):
    response = await client.get("/api/v1/market/summary")
    assert response.status_code in (200, 401)


@pytest.mark.asyncio
async def test_market_overview(client: AsyncClient):
    response = await client.get("/api/v1/market/overview")
    assert response.status_code in (200, 401)


@pytest.mark.asyncio
async def test_market_indices(client: AsyncClient):
    response = await client.get("/api/v1/market/indices")
    assert response.status_code in (200, 401)


@pytest.mark.asyncio
async def test_market_sectors(client: AsyncClient):
    response = await client.get("/api/v1/market/sectors")
    assert response.status_code in (200, 401)

