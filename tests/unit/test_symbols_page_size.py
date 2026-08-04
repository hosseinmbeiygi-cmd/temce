"""Tests for the instruments/symbols page_size validation limit.

The limit was raised from ``le=500`` to ``le=10000`` (apps/api/endpoints/symbols.py)
so the ML page (``/instruments?page_size=10000``) and the backtest page
(``/instruments?page=1&page_size=2000``) can fetch all symbols without a 422
validation error. These tests pin that behaviour and confirm the upper bound
still protects the API from absurd page sizes.

The ``client`` fixture is provided by ``tests/unit/conftest.py``
(session-scoped app, httpx ASGI transport).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_instruments_page_size_10000_accepted(client: AsyncClient):
    """GET /api/v1/instruments?page_size=10000 must be accepted (ML page)."""
    resp = await client.get("/api/v1/instruments", params={"page_size": 10000})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "items" in body["data"]
    assert "total" in body["data"]


@pytest.mark.asyncio
async def test_instruments_page_size_2000_accepted(client: AsyncClient):
    """GET /api/v1/instruments?page=1&page_size=2000 must be accepted (backtest page)."""
    resp = await client.get("/api/v1/instruments", params={"page": 1, "page_size": 2000})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["page"] == 1


@pytest.mark.asyncio
async def test_instruments_page_size_over_limit_rejected(client: AsyncClient):
    """page_size above 10000 must still be rejected with 422 (upper bound kept)."""
    resp = await client.get("/api/v1/instruments", params={"page_size": 10001})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_instruments_default_page_size(client: AsyncClient):
    """Default page_size=50 must still work unchanged."""
    resp = await client.get("/api/v1/instruments")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["page_size"] == 50
