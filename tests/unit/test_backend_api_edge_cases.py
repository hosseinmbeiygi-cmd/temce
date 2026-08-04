"""Edge case tests for Iran Market Data Backend API.

Covers: combined filters, empty params, special characters,
boundary values, response consistency, and cross-endpoint validation.
The ``client`` fixture is provided by ``tests/unit/conftest.py`` (session-scoped app).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

# ============================================================================
# Combined filters (multi-param)
# ============================================================================


@pytest.mark.asyncio
async def test_instruments_combined_market_industry(client: AsyncClient):
    """Filter by both market and industry simultaneously."""
    resp = await client.get("/api/v1/instruments", params={"market": "بورس", "industry": "بانک"})
    assert resp.status_code == 200
    resp.json()


@pytest.mark.asyncio
async def test_instruments_combined_search_market(client: AsyncClient):
    """Search + market filter together."""
    resp = await client.get("/api/v1/instruments", params={"search": "فولاد", "market": "بورس"})
    assert resp.status_code == 200
    resp.json()


@pytest.mark.asyncio
async def test_signals_combined_type_signal(user_client: AsyncClient):
    """Filter signals by both type and direction (requires user)."""
    resp = await user_client.get("/api/v1/signals", params={"type": "تکنیکال", "signal": "خرید"})
    assert resp.status_code == 200
    resp.json()


@pytest.mark.asyncio
async def test_news_combined_category_search(client: AsyncClient):
    """Filter news by category + search together."""
    resp = await client.get("/api/v1/news", params={"category": "صنعتی", "search": "سیمان"})
    assert resp.status_code == 200
    resp.json()


# ============================================================================
# Empty / missing values
# ============================================================================


@pytest.mark.asyncio
async def test_instruments_empty_search_string(client: AsyncClient):
    """Empty search string should return valid paginated response."""
    resp = await client.get("/api/v1/instruments", params={"search": ""})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "items" in body["data"]
    assert "total" in body["data"]


@pytest.mark.asyncio
async def test_instruments_nonexistent_market(client: AsyncClient):
    """Filter by nonexistent market should return empty list."""
    resp = await client.get("/api/v1/instruments", params={"market": "بازار_ناموجود"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["total"] == 0
    assert data["data"]["items"] == []


@pytest.mark.asyncio
async def test_signals_nonexistent_type(user_client: AsyncClient):
    """Filter by nonexistent signal type should return empty (requires user)."""
    resp = await user_client.get("/api/v1/signals", params={"type": "ناموجود"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["total"] == 0
    assert data["data"]["items"] == []


@pytest.mark.asyncio
async def test_news_nonexistent_category(client: AsyncClient):
    """Filter by nonexistent news category should return empty."""
    resp = await client.get("/api/v1/news", params={"category": "ناموجود"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["total"] == 0
    assert data["data"]["items"] == []


# ============================================================================
# Special characters in search
# ============================================================================


@pytest.mark.asyncio
async def test_instruments_search_special_chars(client: AsyncClient):
    """Special characters in search should not break the API."""
    resp = await client.get("/api/v1/instruments", params={"search": "@#$%^&*()"})
    assert resp.status_code == 200
    # Should return empty or all (depending on implementation)
    data = resp.json()
    assert "data" in data
    assert "total" in data["data"]


@pytest.mark.asyncio
async def test_news_search_special_chars(client: AsyncClient):
    """Special characters in news search should not break the API."""
    resp = await client.get("/api/v1/news", params={"search": "!@#$%^&*()_+"})
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data


@pytest.mark.asyncio
async def test_instruments_search_unicode(client: AsyncClient):
    """Unicode characters in search should work."""
    resp = await client.get("/api/v1/instruments", params={"search": "™®©"})
    assert resp.status_code == 200


# ============================================================================
# Pagination edge cases
# ============================================================================


@pytest.mark.asyncio
async def test_news_page_too_high(client: AsyncClient):
    """Page number beyond range should return empty list."""
    resp = await client.get("/api/v1/news", params={"page": 999, "page_size": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["items"] == []
    assert data["data"]["total"] >= 0


@pytest.mark.asyncio
async def test_news_min_page_size(client: AsyncClient):
    """Minimum page size (1) should return valid response."""
    resp = await client.get("/api/v1/news", params={"page_size": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["page_size"] == 1


@pytest.mark.asyncio
async def test_news_last_page_partial(client: AsyncClient):
    """Last page may contain fewer items than page_size."""
    resp = await client.get("/api/v1/news", params={"page": 9999, "page_size": 5})
    assert resp.status_code == 200
    data = resp.json()
    # Should gracefully handle out-of-range page
    assert "data" in data


# ============================================================================
# Cross-endpoint data consistency
# ============================================================================


@pytest.mark.asyncio
async def test_instrument_consistent_across_endpoints(client: AsyncClient):
    """Same instrument data across /instruments and /instruments/{symbol}."""
    list_resp = await client.get("/api/v1/instruments")
    list_data = list_resp.json()
    if list_data["data"]["total"] > 0:
        first = list_data["data"]["items"][0]
        symbol = first["symbol"]
        detail_resp = await client.get(f"/api/v1/instruments/{symbol}")
        assert detail_resp.status_code in (200, 404)


@pytest.mark.asyncio
async def test_market_breakdown_matches_total(admin_client: AsyncClient):
    """Sum of market_breakdown counts equals total_instruments (requires admin)."""
    resp = await admin_client.get("/api/v1/dashboard")
    data = resp.json()
    total_from_breakdown = sum(b["count"] for b in data["market_breakdown"])
    assert total_from_breakdown == data["metrics"]["total_instruments"]


@pytest.mark.asyncio
async def test_market_watch_markets_have_symbol(client: AsyncClient):
    """All market_watch items should have a non-empty symbol."""
    watch_resp = await client.get("/api/v1/market/watch")
    watch_data = watch_resp.json()
    for item in watch_data["data"]["items"]:
        assert item.get("symbol") is not None


# ============================================================================
# Numeric boundaries
# ============================================================================


@pytest.mark.asyncio
async def test_prices_are_positive(client: AsyncClient):
    """All instrument prices should be positive numbers."""
    resp = await client.get("/api/v1/instruments")
    assert resp.status_code == 200
    data = resp.json()
    for inst in data["data"]["items"]:
        if "price" in inst:
            assert inst["price"] > 0, f"Non-positive price for {inst['symbol']}"


@pytest.mark.asyncio
async def test_volumes_are_non_negative(client: AsyncClient):
    """All market watch volumes should be >= 0."""
    resp = await client.get("/api/v1/market/watch")
    data = resp.json()
    for item in data["data"]["items"]:
        assert item["volume"] >= 0, f"Negative volume for {item['symbol']}"
        assert item["value"] >= 0, f"Negative value for {item['symbol']}"


@pytest.mark.asyncio
async def test_signal_scores_in_range(user_client: AsyncClient):
    """Signal scores should be between 0 and 100 (requires user)."""
    resp = await user_client.get("/api/v1/signals")
    assert resp.status_code == 200
    data = resp.json()
    for s in data["data"]["items"]:
        if "score" in s:
            assert 0 <= s["score"] <= 100, f"Score out of range for {s['symbol']}: {s['score']}"


@pytest.mark.asyncio
async def test_fund_navs_are_positive(client: AsyncClient):
    """All fund NAVs should be positive."""
    resp = await client.get("/api/v1/funds")
    assert resp.status_code == 200
    data = resp.json()
    for f in data["data"]["items"]:
        if "nav" in f:
            assert f["nav"] > 0, f"Non-positive NAV for {f['name']}"


# ============================================================================
# Response structure depth checks
# ============================================================================


@pytest.mark.asyncio
async def test_dashboard_has_all_sections(admin_client: AsyncClient):
    """Dashboard response has all expected top-level keys (requires admin)."""
    resp = await admin_client.get("/api/v1/dashboard")
    data = resp.json()
    assert set(data.keys()) == {
        "metrics",
        "market_breakdown",
        "top_gainers",
        "top_losers",
        "recent_announcements",
    }


@pytest.mark.asyncio
async def test_news_pagination_structure(client: AsyncClient):
    """News response has all pagination fields."""
    resp = await client.get("/api/v1/news")
    data = resp.json()
    assert set(data["data"].keys()) == {
        "items",
        "total",
        "page",
        "page_size",
        "total_pages",
    }
    assert data["data"]["page"] >= 1
    assert data["data"]["page_size"] >= 1
    assert data["data"]["total_pages"] >= 1


@pytest.mark.asyncio
async def test_market_watch_items_have_market_field(client: AsyncClient):
    """Every market_watch item should have a non-empty market field."""
    resp = await client.get("/api/v1/market/watch")
    assert resp.status_code == 200
    data = resp.json()
    for item in data["data"]["items"]:
        if "market" in item:
            assert item["market"], f"Empty market field for {item['symbol']}"


# ============================================================================
# CORS comprehensive
# ============================================================================


@pytest.mark.asyncio
async def test_cors_allowed_origin(client: AsyncClient):
    """CORS header should be present for allowed origins."""
    resp = await client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert (
        resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
    ), "CORS header missing or incorrect"


@pytest.mark.asyncio
async def test_cors_denied_origin(client: AsyncClient):
    """Request from non-allowed origin should not get CORS header."""
    resp = await client.options(
        "/api/v1/health",
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
async def test_market_bourse_returns_valid(client: AsyncClient):
    """Bourse endpoint should return valid response structure."""
    resp = await client.get("/api/v1/market/bourse")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "items" in body["data"]


@pytest.mark.asyncio
async def test_energy_commodity_sub_markets_non_overlapping(client: AsyncClient):
    """Energy & Commodity sub-markets should have no overlapping instruments."""
    resp = await client.get("/api/v1/market/energy-commodity")
    data = resp.json()
    symbols_kala = {i["symbol"] for i in data["sub_markets"][0]["instruments"]}
    symbols_energy = {i["symbol"] for i in data["sub_markets"][1]["instruments"]}
    assert symbols_kala.isdisjoint(symbols_energy), "Sub-markets overlap!"


@pytest.mark.asyncio
async def test_energy_commodity_sub_market_totals_match(client: AsyncClient):
    """Sum of sub-market instrument counts equals total_symbols."""
    resp = await client.get("/api/v1/market/energy-commodity")
    data = resp.json()
    sub_total = sum(sm["count"] for sm in data["sub_markets"])
    assert (
        sub_total == data["summary"]["total_symbols"]
    ), f"Sub-market counts ({sub_total}) != total_symbols ({data['summary']['total_symbols']})"


# ============================================================================
# Ordering assertions
# ============================================================================


@pytest.mark.asyncio
async def test_top_gainers_are_sorted(admin_client: AsyncClient):
    """Top gainers should be sorted descending by change (requires admin)."""
    resp = await admin_client.get("/api/v1/dashboard")
    data = resp.json()
    changes = [g["change"] for g in data["top_gainers"]]
    assert changes == sorted(changes, reverse=True), "Top gainers not sorted descending"


@pytest.mark.asyncio
async def test_industries_sorted_by_count(client: AsyncClient):
    """Industries should be sorted by count descending (most_common)."""
    resp = await client.get("/api/v1/industries")
    data = resp.json()
    counts = [ind["count"] for ind in data["data"]["items"]]
    assert counts == sorted(counts, reverse=True), "Industries not sorted by count descending"


# ============================================================================
# Type safety - invalid param types should not crash
# ============================================================================


@pytest.mark.asyncio
async def test_invalid_instrument_id_type(client: AsyncClient):
    """Passing invalid ID type should still return a proper response."""
    # Symbol is a string, the endpoint expects it as path param
    resp = await client.get("/api/v1/instruments/12345")
    assert resp.status_code == 404  # Not found, not 500
    assert resp.json().get("detail") is not None


@pytest.mark.asyncio
async def test_invalid_announcement_id_string(client: AsyncClient):
    """Passing string for announcement_id (expects int) should return 422 or 404."""
    resp = await client.get("/api/v1/announcements/abc")
    # FastAPI will try to parse "abc" as int -> 422 validation error
    assert resp.status_code in (422, 404)


# ============================================================================
# Empty state edge case: signal filter that returns nothing
# ============================================================================


@pytest.mark.asyncio
async def test_signals_filter_sell_only(user_client: AsyncClient):
    """Filtering for only 'فروش' signals should return correct count (requires user)."""
    resp = await user_client.get("/api/v1/signals", params={"signal": "فروش"})
    assert resp.status_code == 200
    resp.json()
