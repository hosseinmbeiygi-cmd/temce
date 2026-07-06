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
async def test_symbol_info(client: AsyncClient):
    response = await client.get("/api/v1/instruments/فولاد")
    assert response.status_code in (200, 401, 404)


@pytest.mark.asyncio
async def test_symbol_detail(client: AsyncClient):
    response = await client.get("/api/v1/instruments/فولاد/detail")
    assert response.status_code in (200, 401, 404)


@pytest.mark.asyncio
async def test_instruments_list(client: AsyncClient):
    response = await client.get("/api/v1/instruments")
    assert response.status_code in (200, 401)


@pytest.mark.asyncio
async def test_instruments_search(client: AsyncClient):
    response = await client.get("/api/v1/instruments/search?q=فولاد")
    assert response.status_code in (200, 401)

