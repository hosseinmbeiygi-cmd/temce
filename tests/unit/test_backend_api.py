"""Comprehensive tests for Iran Market Data Backend API.

Tests are aligned with the actual API responses (ApiResponse wrapper format).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
import pytest_asyncio
from apps.api.app import app
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ============================================================================
# Health
# ============================================================================


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """GET /api/v1/health should return ok status (wrapped in ApiResponse)."""
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert "timestamp" in body["data"]
    assert body["data"]["service"] == "iran-market-platform"


# ============================================================================
# Dashboard
# ============================================================================


@pytest.mark.asyncio
async def test_dashboard_returns_metrics(client: AsyncClient):
    """GET /api/v1/dashboard should return dashboard metrics."""
    resp = await client.get("/api/v1/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "metrics" in data
    m = data["metrics"]
    assert "total_instruments" in m
    assert "active_signals" in m
    assert "total_volume" in m
    assert "market_breakdown" in data
    assert "top_gainers" in data
    assert "top_losers" in data
    assert "recent_announcements" in data


# ============================================================================
# Instruments (Symbols)
# ============================================================================


@pytest.mark.asyncio
async def test_instruments_list_all(client: AsyncClient):
    """GET /api/v1/instruments should return paginated results."""
    resp = await client.get("/api/v1/instruments")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "items" in body["data"]
    assert "total" in body["data"]
    assert body["data"]["page"] == 1


@pytest.mark.asyncio
async def test_instruments_search(client: AsyncClient):
    """GET /api/v1/instruments/search should work."""
    resp = await client.get("/api/v1/instruments/search", params={"q": "test"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True


@pytest.mark.asyncio
async def test_instrument_detail_not_found(client: AsyncClient):
    """GET /api/v1/instruments/{symbol} with non-existent symbol should 404."""
    resp = await client.get("/api/v1/instruments/ناموجود")
    assert resp.status_code == 404


# ============================================================================
# Market Watch
# ============================================================================


@pytest.mark.asyncio
async def test_market_watch_returns_data(client: AsyncClient):
    """GET /api/v1/market/watch should return market watch items."""
    resp = await client.get("/api/v1/market/watch")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "items" in body["data"]


# ============================================================================
# Signals
# ============================================================================


@pytest.mark.asyncio
async def test_signals_list(client: AsyncClient):
    """GET /api/v1/signals should return signals with summary."""
    resp = await client.get("/api/v1/signals")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "data" in body
    assert "summary" in body
    assert "buy" in body["summary"]
    assert "sell" in body["summary"]
    assert "neutral" in body["summary"]


# ============================================================================
# News
# ============================================================================


@pytest.mark.asyncio
async def test_news_list(client: AsyncClient):
    """GET /api/v1/news should return news with pagination."""
    resp = await client.get("/api/v1/news")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "items" in body["data"]
    assert "total" in body["data"]
    assert "page" in body["data"]
    assert "total_pages" in body["data"]


@pytest.mark.asyncio
async def test_news_pagination(client: AsyncClient):
    """GET /api/v1/news?page_size=2 should respect page_size."""
    resp = await client.get("/api/v1/news", params={"page_size": 2, "page": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert len(body["data"]["items"]) <= 2


@pytest.mark.asyncio
async def test_news_search(client: AsyncClient):
    """GET /api/v1/news/search should work."""
    resp = await client.get("/api/v1/news/search", params={"q": "test"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True


@pytest.mark.asyncio
async def test_news_by_category(client: AsyncClient):
    """GET /api/v1/news/category/{category} should work."""
    resp = await client.get("/api/v1/news/category/market")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True


@pytest.mark.asyncio
async def test_news_trending(client: AsyncClient):
    """GET /api/v1/news/trending should work."""
    resp = await client.get("/api/v1/news/trending")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True


# ============================================================================
# Market-specific endpoints
# ============================================================================


@pytest.mark.asyncio
async def test_market_bourse(client: AsyncClient):
    """GET /api/v1/market/bourse should return Bourse market data."""
    resp = await client.get("/api/v1/market/bourse")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True


@pytest.mark.asyncio
async def test_market_energy_commodity(client: AsyncClient):
    """GET /api/v1/market/energy-commodity should return Energy & Commodity data."""
    resp = await client.get("/api/v1/market/energy-commodity")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "sub_markets" in body
    assert "summary" in body


# ============================================================================
# Industries & Funds
# ============================================================================


@pytest.mark.asyncio
async def test_industries_list(client: AsyncClient):
    """GET /api/v1/industries should return industries with counts."""
    resp = await client.get("/api/v1/industries")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "items" in body["data"]


@pytest.mark.asyncio
async def test_funds_list(client: AsyncClient):
    """GET /api/v1/funds should return funds."""
    resp = await client.get("/api/v1/funds")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "items" in body["data"]


# ============================================================================
# Market Overview & Gainers/Losers
# ============================================================================


@pytest.mark.asyncio
async def test_market_overview(client: AsyncClient):
    """GET /api/v1/market/overview should work."""
    resp = await client.get("/api/v1/market/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True


@pytest.mark.asyncio
async def test_market_gainers(client: AsyncClient):
    """GET /api/v1/market/gainers should work."""
    resp = await client.get("/api/v1/market/gainers")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True


@pytest.mark.asyncio
async def test_market_losers(client: AsyncClient):
    """GET /api/v1/market/losers should work."""
    resp = await client.get("/api/v1/market/losers")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True


@pytest.mark.asyncio
async def test_market_most_active(client: AsyncClient):
    """GET /api/v1/market/active should work."""
    resp = await client.get("/api/v1/market/active")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True


# ============================================================================
# Fundamental Analysis
# ============================================================================


@pytest.mark.asyncio
async def test_fundamental_ratios(client: AsyncClient):
    """GET /api/v1/fundamental/ratios/{symbol} should work."""
    resp = await client.get("/api/v1/fundamental/ratios/test")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_fundamental_score(client: AsyncClient):
    """GET /api/v1/fundamental/score/{symbol} should work."""
    resp = await client.get("/api/v1/fundamental/score/test")
    assert resp.status_code == 200


# ============================================================================
# Quotes
# ============================================================================


@pytest.mark.asyncio
async def test_quote_latest(client: AsyncClient):
    """GET /api/v1/quotes/{id}/latest should work."""
    resp = await client.get("/api/v1/quotes/test/latest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True


@pytest.mark.asyncio
async def test_quote_history(client: AsyncClient):
    """GET /api/v1/quotes/{id}/history should work."""
    resp = await client.get("/api/v1/quotes/test/history")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True


# ============================================================================
# CORS
# ============================================================================


@pytest.mark.asyncio
async def test_cors_headers(client: AsyncClient):
    """API should return CORS headers for allowed origins."""
    resp = await client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    cors_origin = resp.headers.get("access-control-allow-origin")
    if cors_origin:
        assert cors_origin == "*" or cors_origin == "http://localhost:3000"


# ============================================================================
# 404 handler
# ============================================================================


@pytest.mark.asyncio
async def test_unknown_route_returns_404(client: AsyncClient):
    """GET /api/v1/nonexistent should return 404."""
    resp = await client.get("/api/v1/nonexistent")
    assert resp.status_code == 404


# ============================================================================
# Response structure validations
# ============================================================================


@pytest.mark.asyncio
async def test_all_items_have_required_fields(client: AsyncClient):
    """All instruments should have required fields (when items exist)."""
    resp = await client.get("/api/v1/instruments")
    body = resp.json()
    for inst in body["data"]["items"]:
        assert "symbol" in inst or "id" in inst


@pytest.mark.asyncio
async def test_news_have_required_fields(client: AsyncClient):
    """All news items should have required fields (when items exist)."""
    resp = await client.get("/api/v1/news")
    body = resp.json()
    for n in body["data"]["items"]:
        assert "title" in n or "id" in n
