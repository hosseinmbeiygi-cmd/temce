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
    response = await client.get("/admin/dashboard")
    assert response.status_code in (200, 401, 403)


@pytest.mark.asyncio
async def test_admin_system_status(client: AsyncClient):
    response = await client.get("/admin/dashboard/health")
    assert response.status_code in (200, 401, 403)


@pytest.mark.asyncio
async def test_admin_providers(client: AsyncClient):
    response = await client.get("/admin/providers/")
    assert response.status_code in (200, 401, 403)


@pytest.mark.asyncio
async def test_admin_jobs(client: AsyncClient):
    response = await client.get("/admin/jobs/")
    assert response.status_code in (200, 401, 403)


@pytest.mark.asyncio
async def test_admin_schedulers(client: AsyncClient):
    response = await client.get("/admin/models/")
    assert response.status_code in (200, 401, 403)


@pytest.mark.asyncio
async def test_admin_storage(client: AsyncClient):
    response = await client.get("/admin/audit/")
    assert response.status_code in (200, 401, 403)
