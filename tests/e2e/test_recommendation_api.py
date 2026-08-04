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
async def test_recommendations_list(client: AsyncClient):
    response = await client.get("/api/v1/recommendations")
    assert response.status_code in (200, 401)


@pytest.mark.asyncio
async def test_recommendations_create(client: AsyncClient):
    payload = {
        "instrument_id": "فولاد",
        "action": "buy",
        "strategy": "value",
        "risk_tolerance": "moderate",
    }
    response = await client.post("/api/v1/recommendations", json=payload)
    assert response.status_code in (200, 201, 401, 422)
