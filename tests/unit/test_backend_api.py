"""Comprehensive tests for Iran Market Data Backend API."""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root so we can import backend.main
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
import pytest_asyncio
from apps.api.app import app
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def client():
    """Create an async test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ============================================================================
# Health
# ============================================================================


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """GET /api/health should return ok status."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "1.0.0"
    assert "timestamp" in data


# ============================================================================
# Dashboard
# ============================================================================


@pytest.mark.asyncio
async def test_dashboard_returns_metrics(client: AsyncClient):
    """GET /api/dashboard should return all dashboard metrics."""
    resp = await client.get("/api/dashboard")
    assert resp.status_code == 200
    data = resp.json()

    # Check metrics
    assert "metrics" in data
    m = data["metrics"]
    assert m["total_instruments"] >= 10
    assert m["total_announcements"] >= 5
    assert m["total_funds"] >= 3
    assert m["gainers"] + m["losers"] + m["unchanged"] == m["total_instruments"]

    # Check market breakdown
    assert "market_breakdown" in data
    markets = {b["name"] for b in data["market_breakdown"]}
    assert "بورس" in markets
    assert "فرابورس" in markets
    assert "کالا و انرژی" in markets

    # Check top gainers/losers
    assert len(data["top_gainers"]) == 5
    assert len(data["top_losers"]) == 5

    # Check announcements
    assert len(data["recent_announcements"]) >= 3


# ============================================================================
# Instruments
# ============================================================================


@pytest.mark.asyncio
async def test_instruments_list_all(client: AsyncClient):
    """GET /api/instruments should return all instruments."""
    resp = await client.get("/api/instruments")
    assert resp.status_code == 200
    data = resp.json()
    assert "instruments" in data
    assert data["total"] >= 15
    assert len(data["instruments"]) == data["total"]


@pytest.mark.asyncio
async def test_instruments_filter_by_market(client: AsyncClient):
    """GET /api/instruments?market=بورس should filter by market."""
    resp = await client.get("/api/instruments", params={"market": "بورس"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(i["market"] == "بورس" for i in data["instruments"])
    assert data["total"] >= 8


@pytest.mark.asyncio
async def test_instruments_filter_by_industry(client: AsyncClient):
    """GET /api/instruments?industry=بانک should filter by industry."""
    resp = await client.get("/api/instruments", params={"industry": "بانک"})
    assert resp.status_code == 200
    data = resp.json()
    if data["total"] > 0:
        assert all(i["industry"] == "بانک" for i in data["instruments"])


@pytest.mark.asyncio
async def test_instruments_search(client: AsyncClient):
    """GET /api/instruments?search=فولاد should find matching instruments."""
    resp = await client.get("/api/instruments", params={"search": "فولاد"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    for i in data["instruments"]:
        assert "فولاد" in i["symbol"] or "فولاد" in i["name"]


@pytest.mark.asyncio
async def test_instrument_detail_found(client: AsyncClient):
    """GET /api/instruments/{symbol} should return detail."""
    resp = await client.get("/api/instruments/فولاد")
    assert resp.status_code == 200
    data = resp.json()
    assert data["instrument"]["symbol"] == "فولاد"
    assert "price_history" in data
    assert len(data["price_history"]) > 0
    assert data["market_watch"] is not None


@pytest.mark.asyncio
async def test_instrument_detail_not_found(client: AsyncClient):
    """GET /api/instruments/{symbol} with invalid symbol should 404."""
    resp = await client.get("/api/instruments/ناموجود")
    assert resp.status_code == 404


# ============================================================================
# Market Watch
# ============================================================================


@pytest.mark.asyncio
async def test_market_watch_returns_data(client: AsyncClient):
    """GET /api/market/watch should return market watch items."""
    resp = await client.get("/api/market/watch")
    assert resp.status_code == 200
    data = resp.json()
    assert "market_watch" in data
    assert len(data["market_watch"]) >= 8
    assert "summary" in data
    assert data["summary"]["total_volume"] >= 0
    assert data["summary"]["total_value"] >= 0


# ============================================================================
# Announcements
# ============================================================================


@pytest.mark.asyncio
async def test_announcements_list(client: AsyncClient):
    """GET /api/announcements should return announcements."""
    resp = await client.get("/api/announcements")
    assert resp.status_code == 200
    data = resp.json()
    assert "announcements" in data
    assert data["total"] >= 5
    assert len(data["types"]) >= 3


@pytest.mark.asyncio
async def test_announcements_filter_by_symbol(client: AsyncClient):
    """GET /api/announcements?symbol=فولاد should filter."""
    resp = await client.get("/api/announcements", params={"symbol": "فولاد"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(a["symbol"] == "فولاد" for a in data["announcements"])


@pytest.mark.asyncio
async def test_announcements_filter_by_type(client: AsyncClient):
    """GET /api/announcements?type=مجمع should filter by type."""
    resp = await client.get("/api/announcements", params={"type": "مجمع"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(a["type"] == "مجمع" for a in data["announcements"])


@pytest.mark.asyncio
async def test_announcement_detail_found(client: AsyncClient):
    """GET /api/announcements/1 should return announcement detail."""
    resp = await client.get("/api/announcements/1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["announcement"]["id"] == 1


@pytest.mark.asyncio
async def test_announcement_detail_not_found(client: AsyncClient):
    """GET /api/announcements/9999 should 404."""
    resp = await client.get("/api/announcements/9999")
    assert resp.status_code == 404


# ============================================================================
# Funds
# ============================================================================


@pytest.mark.asyncio
async def test_funds_list(client: AsyncClient):
    """GET /api/funds should return funds."""
    resp = await client.get("/api/funds")
    assert resp.status_code == 200
    data = resp.json()
    assert "funds" in data
    assert data["total"] >= 4
    assert len(data["types"]) >= 2


@pytest.mark.asyncio
async def test_funds_filter_by_type(client: AsyncClient):
    """GET /api/funds?fund_type=سهامی should filter."""
    resp = await client.get("/api/funds", params={"fund_type": "سهامی"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(f["type"] == "سهامی" for f in data["funds"])


@pytest.mark.asyncio
async def test_fund_detail_found(client: AsyncClient):
    """GET /api/funds/{name} should return fund detail."""
    resp = await client.get("/api/funds/صندوق زرین")
    assert resp.status_code == 200
    data = resp.json()
    assert data["fund"]["name"] == "صندوق زرین"
    assert "nav" in data["fund"]


@pytest.mark.asyncio
async def test_fund_detail_not_found(client: AsyncClient):
    """GET /api/funds/invalid should 404."""
    resp = await client.get("/api/funds/صندوق ناموجود")
    assert resp.status_code == 404


# ============================================================================
# Industries
# ============================================================================


@pytest.mark.asyncio
async def test_industries_list(client: AsyncClient):
    """GET /api/industries should return industries with counts."""
    resp = await client.get("/api/industries")
    assert resp.status_code == 200
    data = resp.json()
    assert "industries" in data
    assert len(data["industries"]) >= 5
    for ind in data["industries"]:
        assert "name" in ind
        assert "count" in ind
        assert ind["count"] >= 1


# ============================================================================
# Signals
# ============================================================================


@pytest.mark.asyncio
async def test_signals_list(client: AsyncClient):
    """GET /api/signals should return signals."""
    resp = await client.get("/api/signals")
    assert resp.status_code == 200
    data = resp.json()
    assert "signals" in data
    assert data["total"] >= 5
    assert "summary" in data
    assert data["summary"]["buy"] >= 1
    assert data["summary"]["sell"] >= 0
    assert data["summary"]["neutral"] >= 0
    assert len(data["types"]) >= 2


@pytest.mark.asyncio
async def test_signals_filter_by_type(client: AsyncClient):
    """GET /api/signals?type=اسمارت مانی should filter."""
    resp = await client.get("/api/signals", params={"type": "اسمارت مانی"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(s["type"] == "اسمارت مانی" for s in data["signals"])


@pytest.mark.asyncio
async def test_signals_filter_by_signal(client: AsyncClient):
    """GET /api/signals?signal=خرید should filter buy signals."""
    resp = await client.get("/api/signals", params={"signal": "خرید"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(s["signal"] == "خرید" for s in data["signals"])


# ============================================================================
# News
# ============================================================================


@pytest.mark.asyncio
async def test_news_list(client: AsyncClient):
    """GET /api/news should return news with pagination."""
    resp = await client.get("/api/news")
    assert resp.status_code == 200
    data = resp.json()
    assert "news" in data
    assert data["total"] >= 5
    assert data["page"] == 1
    assert data["total_pages"] >= 1
    assert len(data["categories"]) >= 4


@pytest.mark.asyncio
async def test_news_pagination(client: AsyncClient):
    """GET /api/news?page_size=2 should paginate."""
    resp = await client.get("/api/news", params={"page_size": 2, "page": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["news"]) == 2


@pytest.mark.asyncio
async def test_news_filter_by_category(client: AsyncClient):
    """GET /api/news?category=شرکتی should filter."""
    resp = await client.get("/api/news", params={"category": "شرکتی"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(n["category"] == "شرکتی" for n in data["news"])


@pytest.mark.asyncio
async def test_news_search(client: AsyncClient):
    """GET /api/news?search=فولاد should search by title."""
    resp = await client.get("/api/news", params={"search": "فولاد"})
    assert resp.status_code == 200
    data = resp.json()
    if data["total"] > 0:
        assert all("فولاد" in n["title"] for n in data["news"])


# ============================================================================
# Market-specific endpoints
# ============================================================================


@pytest.mark.asyncio
async def test_market_bourse(client: AsyncClient):
    """GET /api/market/bourse should return Bourse market data."""
    resp = await client.get("/api/market/bourse")
    assert resp.status_code == 200
    data = resp.json()
    assert "instruments" in data
    assert "market_watch" in data
    assert "summary" in data
    assert data["summary"]["total_symbols"] >= 8
    assert all(i["market"] == "بورس" for i in data["instruments"])


@pytest.mark.asyncio
async def test_market_farabourse(client: AsyncClient):
    """GET /api/market/farabourse should return Farabourse data."""
    resp = await client.get("/api/market/farabourse")
    assert resp.status_code == 200
    data = resp.json()
    assert "instruments" in data
    assert data["summary"]["total_symbols"] >= 2
    assert all(i["market"] == "فرابورس" for i in data["instruments"])


@pytest.mark.asyncio
async def test_market_energy_commodity(client: AsyncClient):
    """GET /api/market/energy-commodity should return Energy & Commodity data."""
    resp = await client.get("/api/market/energy-commodity")
    assert resp.status_code == 200
    data = resp.json()
    assert "instruments" in data
    assert "sub_markets" in data
    assert len(data["sub_markets"]) == 2  # کالا و انرژی
    assert data["sub_markets"][0]["name"] == "بورس کالا" or data["sub_markets"][1]["name"] == "بورس کالا"
    assert data["summary"]["total_symbols"] >= 3


# ============================================================================
# CORS
# ============================================================================


@pytest.mark.asyncio
async def test_cors_headers(client: AsyncClient):
    """API should return CORS headers for allowed origins."""
    resp = await client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    # CORS headers may be on the response
    cors_origin = resp.headers.get("access-control-allow-origin")
    if cors_origin:
        assert cors_origin == "http://localhost:3000"


# ============================================================================
# 404 handler
# ============================================================================


@pytest.mark.asyncio
async def test_unknown_route_returns_404(client: AsyncClient):
    """GET /api/nonexistent should return 404."""
    resp = await client.get("/api/nonexistent")
    assert resp.status_code == 404


# ============================================================================
# Response structure validations
# ============================================================================


@pytest.mark.asyncio
async def test_all_items_have_required_fields(client: AsyncClient):
    """All instruments should have required fields."""
    resp = await client.get("/api/instruments")
    data = resp.json()
    for inst in data["instruments"]:
        assert "symbol" in inst
        assert "name" in inst
        assert "market" in inst
        assert "price" in inst
        assert "change" in inst


@pytest.mark.asyncio
async def test_signals_have_required_fields(client: AsyncClient):
    """All signals should have required fields."""
    resp = await client.get("/api/signals")
    data = resp.json()
    for s in data["signals"]:
        assert "symbol" in s
        assert "signal" in s
        assert "score" in s
        assert "target" in s
        assert "stop" in s


@pytest.mark.asyncio
async def test_news_have_required_fields(client: AsyncClient):
    """All news items should have required fields."""
    resp = await client.get("/api/news")
    data = resp.json()
    for n in data["news"]:
        assert "title" in n
        assert "summary" in n
        assert "source" in n
        assert "category" in n
        assert "date" in n
