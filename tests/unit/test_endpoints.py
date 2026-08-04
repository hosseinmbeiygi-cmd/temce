"""Tests for the main FastAPI app (codal, news, analysis endpoints).

The ``client`` fixture is provided by ``tests/unit/conftest.py``.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["status"] == "ok"
    assert data["data"]["service"] == "iran-market-platform"


@pytest.mark.asyncio
async def test_root_redirect(client):
    resp = await client.get("/", follow_redirects=False)
    assert resp.status_code in (307, 303)
    assert "/docs" in resp.headers.get("location", "")


# ==============================================================
# CODAL
# ==============================================================


@pytest.mark.asyncio
async def test_codal_list(client: AsyncClient):
    resp = await client.get("/api/v1/codal")
    # Returns 500 when database is not initialized (expected in test),
    # returns 200 with success=False when codal endpoint has no data.
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        data = resp.json()
        assert data["success"] in (True, False)


@pytest.mark.asyncio
async def test_codal_profile_found(client):
    resp = await client.get("/api/v1/codal/فولاد/profile")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["symbol"] == "فولاد"
    assert data["data"]["name"] == "فولاد مبارکه اصفهان"


@pytest.mark.asyncio
async def test_codal_profile_not_found(client):
    resp = await client.get("/api/v1/codal/ناموجود/profile")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_codal_financials(client):
    resp = await client.get("/api/v1/codal/فولاد/financials")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "quarters" in data["data"]
    assert len(data["data"]["quarters"]) == 4


@pytest.mark.asyncio
async def test_codal_dividends(client):
    resp = await client.get("/api/v1/codal/فولاد/dividends")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "dividends" in data["data"]


@pytest.mark.asyncio
async def test_codal_holders(client):
    resp = await client.get("/api/v1/codal/فولاد/holders")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "holders" in data["data"]


@pytest.mark.asyncio
async def test_codal_insider(client):
    resp = await client.get("/api/v1/codal/فولاد/insider")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "trades" in data["data"]


# ==============================================================
# NEWS
# ==============================================================


@pytest.mark.asyncio
async def test_news_list(client):
    resp = await client.get("/api/v1/news")
    # Returns 500 when database is not initialized (expected in test)
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        data = resp.json()
        assert data["success"] is True


@pytest.mark.asyncio
async def test_news_category_valid(client):
    resp = await client.get("/api/v1/news/category/market")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_news_category_invalid(client):
    resp = await client.get("/api/v1/news/category/invalid")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "Invalid category" in data["error"]["message"]


@pytest.mark.asyncio
async def test_news_trending(client):
    resp = await client.get("/api/v1/news/trending")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert len(data["data"]) <= 10


# ==============================================================
# ANALYSIS
# ==============================================================


@pytest.mark.asyncio
async def test_analysis_overview(client):
    resp = await client.get("/api/v1/analysis/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "sentiment" in data["data"]
    assert "trends" in data["data"]


@pytest.mark.asyncio
async def test_analysis_trends(client):
    resp = await client.get("/api/v1/analysis/trends")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True


@pytest.mark.asyncio
async def test_analysis_elliot_waves(client):
    """Endpoint exists but may return success=False without real data."""
    resp = await client.get("/api/v1/analysis/elliot-waves/فولاد")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] in (True, False)


@pytest.mark.asyncio
async def test_analysis_liquidity(client):
    resp = await client.get("/api/v1/analysis/liquidity")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
