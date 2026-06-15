from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from apps.admin.app import admin_app as app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_admin_stats(client: AsyncClient):
    response = await client.get("/api/v1/admin/stats")
    assert response.status_code in (200, 401, 403)


@pytest.mark.asyncio
async def test_admin_system_status(client: AsyncClient):
    response = await client.get("/api/v1/admin/system/status")
    assert response.status_code in (200, 401, 403)


@pytest.mark.asyncio
async def test_admin_providers(client: AsyncClient):
    response = await client.get("/api/v1/admin/providers")
    assert response.status_code in (200, 401, 403)


@pytest.mark.asyncio
async def test_admin_jobs(client: AsyncClient):
    response = await client.get("/api/v1/admin/jobs")
    assert response.status_code in (200, 401, 403)


@pytest.mark.asyncio
async def test_admin_schedulers(client: AsyncClient):
    response = await client.get("/api/v1/admin/schedulers")
    assert response.status_code in (200, 401, 403)


@pytest.mark.asyncio
async def test_admin_storage(client: AsyncClient):
    response = await client.get("/api/v1/admin/storage/usage")
    assert response.status_code in (200, 401, 403)
