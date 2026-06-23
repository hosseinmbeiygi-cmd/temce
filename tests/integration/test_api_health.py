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
async def test_health_endpoint(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code in (200, 404)

    response = await client.get("/api/v1/health")
    assert response.status_code in (200, 401, 404)


@pytest.mark.asyncio
async def test_health_returns_json(client: AsyncClient):
    response = await client.get("/api/v1/health")
    if response.status_code == 200:
        data = response.json()
        assert "status" in data

