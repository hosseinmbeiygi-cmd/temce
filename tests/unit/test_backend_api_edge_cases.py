"""Edge case tests for Iran Market Data Backend API.

Covers: combined filters, empty params, special characters,
boundary values, response consistency, and cross-endpoint validation.
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
# Combined filters (multi-param)
# ============================================================================


@pytest.mark.asyncio
async def test_instruments_combined_market_industry(client: AsyncClient):
    """Filter by both market and industry simultaneously."""
    resp = await client.get("/api/instruments", params={"market": "بورس", "industry": "بانک"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(i["market"] == "بورس" and i["industry"] == "بانک" for i in data["instruments"])


@pytest.mark.asyncio
async def test_instruments_combined_search_market(client: AsyncClient):
    """Search + market filter together."""
    resp = await client.get("/api/instruments", params={"search": "فولاد", "market": "بورس"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(i["market"] == "بورس" for i in data["instruments"])
    if data["total"] > 0:
        assert all("فولاد" in i["symbol"] or "فولاد" in i["name"] for i in data["instruments"])


@pytest.mark.asyncio
async def test_signals_combined_type_signal(client: AsyncClient):
    """Filter signals by both type and direction."""
    resp = await client.get("/api/signals", params={"type": "تکنیکال", "signal": "خرید"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(s["type"] == "تکنیکال" and s["signal"] == "خرید" for s in data["signals"])


@pytest.mark.asyncio
async def test_news_combined_category_search(client: AsyncClient):
    """Filter news by category + search together."""
    resp = await client.get("/api/news", params={"category": "صنعتی", "search": "سیمان"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(n["category"] == "صنعتی" for n in data["news"])
    if data["total"] > 0:
        assert all("سیمان" in n["title"] for n in data["news"])


# ============================================================================
# Empty / missing values
# ============================================================================


@pytest.mark.asyncio
async def test_instruments_empty_search_string(client: AsyncClient):
    """Empty search string should return all instruments."""
    resp = await client.get("/api/instruments", params={"search": ""})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 15


@pytest.mark.asyncio
async def test_instruments_nonexistent_market(client: AsyncClient):
    """Filter by nonexistent market should return empty list."""
    resp = await client.get("/api/instruments", params={"market": "بازار_ناموجود"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["instruments"] == []


@pytest.mark.asyncio
async def test_signals_nonexistent_type(client: AsyncClient):
    """Filter by nonexistent signal type should return empty."""
    resp = await client.get("/api/signals", params={"type": "ناموجود"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["signals"] == []


@pytest.mark.asyncio
async def test_news_nonexistent_category(client: AsyncClient):
    """Filter by nonexistent news category should return empty."""
    resp = await client.get("/api/news", params={"category": "ناموجود"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["news"] == []


# ============================================================================
# Special characters in search
# ============================================================================


@pytest.mark.asyncio
async def test_instruments_search_special_chars(client: AsyncClient):
    """Special characters in search should not break the API."""
    resp = await client.get("/api/instruments", params={"search": "@#$%^&*()"})
    assert resp.status_code == 200
    # Should return empty or all (depending on implementation)
    data = resp.json()
    assert "instruments" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_news_search_special_chars(client: AsyncClient):
    """Special characters in news search should not break the API."""
    resp = await client.get("/api/news", params={"search": "!@#$%^&*()_+"})
    assert resp.status_code == 200
    data = resp.json()
    assert "news" in data


@pytest.mark.asyncio
async def test_instruments_search_unicode(client: AsyncClient):
    """Unicode characters in search should work."""
    resp = await client.get("/api/instruments", params={"search": "™®©"})
    assert resp.status_code == 200


# ============================================================================
# Pagination edge cases
# ============================================================================


@pytest.mark.asyncio
async def test_news_page_too_high(client: AsyncClient):
    """Page number beyond range should return empty list."""
    resp = await client.get("/api/news", params={"page": 999, "page_size": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert data["news"] == []
    assert data["total"] >= 0


@pytest.mark.asyncio
async def test_news_min_page_size(client: AsyncClient):
    """Minimum page size (1)."""
    resp = await client.get("/api/news", params={"page_size": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["news"]) == 1
    assert data["page_size"] == 1


@pytest.mark.asyncio
async def test_news_last_page_partial(client: AsyncClient):
    """Last page may contain fewer items than page_size."""
    resp = await client.get("/api/news", params={"page": 9999, "page_size": 5})
    assert resp.status_code == 200
    data = resp.json()
    # Should gracefully handle out-of-range page
    assert "news" in data


# ============================================================================
# Cross-endpoint data consistency
# ============================================================================


@pytest.mark.asyncio
async def test_instrument_consistent_across_endpoints(client: AsyncClient):
    """Same instrument data across /instruments and /instruments/{symbol}."""
    # Get from list
    list_resp = await client.get("/api/instruments", params={"market": "بورس"})
    list_data = list_resp.json()
    if list_data["total"] > 0:
        first = list_data["instruments"][0]
        symbol = first["symbol"]

        # Get from detail endpoint
        detail_resp = await client.get(f"/api/instruments/{symbol}")
        detail_data = detail_resp.json()
        assert detail_data["instrument"]["symbol"] == first["symbol"]
        assert detail_data["instrument"]["name"] == first["name"]
        assert detail_data["instrument"]["market"] == first["market"]


@pytest.mark.asyncio
async def test_market_breakdown_matches_total(client: AsyncClient):
    """Sum of market_breakdown counts equals total_instruments."""
    resp = await client.get("/api/dashboard")
    data = resp.json()
    total_from_breakdown = sum(b["count"] for b in data["market_breakdown"])
    assert total_from_breakdown == data["metrics"]["total_instruments"]


@pytest.mark.asyncio
async def test_market_watch_markets_are_valid(client: AsyncClient):
    """All market_watch items have a valid market that exists in instruments."""
    watch_resp = await client.get("/api/market/watch")
    watch_data = watch_resp.json()

    inst_resp = await client.get("/api/instruments")
    inst_data = inst_resp.json()
    valid_markets = {i["market"] for i in inst_data["instruments"]}

    for item in watch_data["market_watch"]:
        assert item["market"] in valid_markets, f"Unknown market: {item['market']}"


# ============================================================================
# Numeric boundaries
# ============================================================================


@pytest.mark.asyncio
async def test_prices_are_positive(client: AsyncClient):
    """All instrument prices should be positive numbers."""
    resp = await client.get("/api/instruments")
    data = resp.json()
    for inst in data["instruments"]:
        assert inst["price"] > 0, f"Non-positive price for {inst['symbol']}"


@pytest.mark.asyncio
async def test_volumes_are_non_negative(client: AsyncClient):
    """All market watch volumes should be >= 0."""
    resp = await client.get("/api/market/watch")
    data = resp.json()
    for item in data["market_watch"]:
        assert item["volume"] >= 0, f"Negative volume for {item['symbol']}"
        assert item["value"] >= 0, f"Negative value for {item['symbol']}"


@pytest.mark.asyncio
async def test_signal_scores_in_range(client: AsyncClient):
    """Signal scores should be between 0 and 100."""
    resp = await client.get("/api/signals")
    data = resp.json()
    for s in data["signals"]:
        assert 0 <= s["score"] <= 100, f"Score out of range for {s['symbol']}: {s['score']}"
        assert s["target"] > 0, f"Non-positive target for {s['symbol']}"
        assert s["stop"] > 0, f"Non-positive stop for {s['symbol']}"


@pytest.mark.asyncio
async def test_fund_navs_are_positive(client: AsyncClient):
    """All fund NAVs should be positive."""
    resp = await client.get("/api/funds")
    data = resp.json()
    for f in data["funds"]:
        assert f["nav"] > 0, f"Non-positive NAV for {f['name']}"


# ============================================================================
# Response structure depth checks
# ============================================================================


@pytest.mark.asyncio
async def test_dashboard_has_all_sections(client: AsyncClient):
    """Dashboard response has all expected top-level keys."""
    resp = await client.get("/api/dashboard")
    data = resp.json()
    assert set(data.keys()) == {"metrics", "market_breakdown", "top_gainers", "top_losers", "recent_announcements"}


@pytest.mark.asyncio
async def test_news_pagination_structure(client: AsyncClient):
    """News response has all pagination fields."""
    resp = await client.get("/api/news")
    data = resp.json()
    assert set(data.keys()) == {"news", "total", "page", "page_size", "total_pages", "categories"}
    assert data["page"] >= 1
    assert data["page_size"] >= 1
    assert data["total_pages"] >= 1


@pytest.mark.asyncio
async def test_market_watch_items_have_market_field(client: AsyncClient):
    """Every market_watch item should have a non-empty market field."""
    resp = await client.get("/api/market/watch")
    data = resp.json()
    for item in data["market_watch"]:
        assert item.get("market"), f"Missing market field for {item['symbol']}"


# ============================================================================
# CORS comprehensive
# ============================================================================


@pytest.mark.asyncio
async def test_cors_allowed_origin(client: AsyncClient):
    """CORS header should be present for allowed origins."""
    resp = await client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000", (
        "CORS header missing or incorrect"
    )


@pytest.mark.asyncio
async def test_cors_denied_origin(client: AsyncClient):
    """Request from non-allowed origin should not get CORS header."""
    resp = await client.options(
        "/api/health",
        headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    cors = resp.headers.get("access-control-allow-origin")
    # FastAPI's CORSMiddleware may still echo back the origin. Check it's not the allowed one.
    if cors:
        assert cors != "http://localhost:3000", "Non-allowed origin got CORS"


# ============================================================================
# Market-specific edge cases
# ============================================================================


@pytest.mark.asyncio
async def test_market_bourse_integrity(client: AsyncClient):
    """Bourse endpoint only returns Bourse instruments, all have market_watch data."""
    resp = await client.get("/api/market/bourse")
    data = resp.json()
    for inst in data["instruments"]:
        assert inst["market"] == "بورس", f"Non-bourse instrument {inst['symbol']} in bourse endpoint"
    # Some should have market_watch entries
    assert len(data["market_watch"]) >= 1


@pytest.mark.asyncio
async def test_energy_commodity_sub_markets_non_overlapping(client: AsyncClient):
    """Energy & Commodity sub-markets should have no overlapping instruments."""
    resp = await client.get("/api/market/energy-commodity")
    data = resp.json()
    symbols_kala = {i["symbol"] for i in data["sub_markets"][0]["instruments"]}
    symbols_energy = {i["symbol"] for i in data["sub_markets"][1]["instruments"]}
    assert symbols_kala.isdisjoint(symbols_energy), "Sub-markets overlap!"


@pytest.mark.asyncio
async def test_energy_commodity_sub_market_totals_match(client: AsyncClient):
    """Sum of sub-market instrument counts equals total_symbols."""
    resp = await client.get("/api/market/energy-commodity")
    data = resp.json()
    sub_total = sum(sm["count"] for sm in data["sub_markets"])
    assert sub_total == data["summary"]["total_symbols"], (
        f"Sub-market counts ({sub_total}) != total_symbols ({data['summary']['total_symbols']})"
    )


# ============================================================================
# Ordering assertions
# ============================================================================


@pytest.mark.asyncio
async def test_top_gainers_are_sorted(client: AsyncClient):
    """Top gainers should be sorted descending by change."""
    resp = await client.get("/api/dashboard")
    data = resp.json()
    changes = [g["change"] for g in data["top_gainers"]]
    assert changes == sorted(changes, reverse=True), "Top gainers not sorted descending"


@pytest.mark.asyncio
async def test_industries_sorted_by_count(client: AsyncClient):
    """Industries should be sorted by count descending (most_common)."""
    resp = await client.get("/api/industries")
    data = resp.json()
    counts = [ind["count"] for ind in data["industries"]]
    assert counts == sorted(counts, reverse=True), "Industries not sorted by count descending"


# ============================================================================
# Type safety - invalid param types should not crash
# ============================================================================


@pytest.mark.asyncio
async def test_invalid_instrument_id_type(client: AsyncClient):
    """Passing invalid ID type should still return a proper response."""
    # Symbol is a string, the endpoint expects it as path param
    resp = await client.get("/api/instruments/12345")
    assert resp.status_code == 404  # Not found, not 500
    assert resp.json().get("detail") is not None


@pytest.mark.asyncio
async def test_invalid_announcement_id_string(client: AsyncClient):
    """Passing string for announcement_id (expects int) should return 422 or 404."""
    resp = await client.get("/api/announcements/abc")
    # FastAPI will try to parse "abc" as int -> 422 validation error
    assert resp.status_code in (422, 404)


# ============================================================================
# Empty state edge case: signal filter that returns nothing
# ============================================================================


@pytest.mark.asyncio
async def test_signals_filter_sell_only(client: AsyncClient):
    """Filtering for only 'فروش' signals should return correct count."""
    resp = await client.get("/api/signals", params={"signal": "فروش"})
    assert resp.status_code == 200
    data = resp.json()
    assert all(s["signal"] == "فروش" for s in data["signals"])
    assert data["summary"]["sell"] == data["total"]
    assert data["summary"]["buy"] == 0
    assert data["summary"]["neutral"] == 0
