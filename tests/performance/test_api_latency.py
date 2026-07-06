from __future__ import annotations

import time

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from apps.api.app import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
@pytest.mark.performance
async def test_health_endpoint_latency(client: AsyncClient):
    latencies = []
    for _ in range(10):
        start = time.monotonic()
        await client.get("/api/v1/health")
        elapsed = (time.monotonic() - start) * 1000
        latencies.append(elapsed)
    avg_latency = sum(latencies) / len(latencies)
    assert avg_latency < 500, f"Average latency {avg_latency:.2f}ms exceeds 500ms threshold"


@pytest.mark.asyncio
@pytest.mark.performance
async def test_instruments_list_latency(client: AsyncClient):
    start = time.monotonic()
    await client.get("/api/v1/instruments")
    elapsed = (time.monotonic() - start) * 1000
    assert elapsed < 1000, f"Instruments list latency {elapsed:.2f}ms exceeds 1000ms threshold"

