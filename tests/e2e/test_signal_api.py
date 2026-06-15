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
async def test_signals_list(client: AsyncClient):
    response = await client.get("/api/v1/signals")
    assert response.status_code in (200, 401)


@pytest.mark.asyncio
async def test_signals_for_symbol(client: AsyncClient):
    response = await client.get("/api/v1/signals/فولاد")
    assert response.status_code in (200, 401, 404)


@pytest.mark.asyncio
async def test_signals_generate(client: AsyncClient):
    payload = {"symbol": "فولاد"}
    response = await client.post("/api/v1/signals/generate", json=payload)
    assert response.status_code in (200, 201, 401, 422)
