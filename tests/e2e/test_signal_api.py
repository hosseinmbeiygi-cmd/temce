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
async def test_signals_list(client: AsyncClient):
    response = await client.get("/api/v1/signals")
    assert response.status_code in (200, 401)


@pytest.mark.asyncio
async def test_signals_for_symbol(client: AsyncClient):
    response = await client.get("/api/v1/signals/فولاد")
    assert response.status_code in (200, 401, 404)


@pytest.mark.asyncio
async def test_signals_generate(client: AsyncClient):
    payload = {"signal_type": "bullish", "score": 0.75, "confidence": 0.8}
    response = await client.post("/api/v1/signals/فولاد", json=payload)
    assert response.status_code in (200, 201, 401, 422)

