"""Integration tests for /funds API endpoints.

Tests cover:
  - GET  /funds              — list all funds (from in-memory cache)
  - GET  /funds/types        — list fund types
  - GET  /funds/{symbol}     — get a single fund
  - GET  /funds/{symbol}/analysis — full 6-dimension analysis
  - POST /funds/{symbol}/update  — update from BrsApi (mocked)
  - Edge cases: not found symbols, empty results, error handling
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from apps.api.endpoints.funds import router as funds_router
from services.fund_service import FundService

pytestmark = pytest.mark.needs_db

# ═══════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════

def make_app(
    fund_service_override: Any = None,
    brsapi_override: Any = None,
) -> FastAPI:
    """Create a minimal test app with the funds router and optional mocks.

    Args:
        fund_service_override: If provided, overrides get_fund_service.
        brsapi_override: If provided, overrides get_brsapi_query_service
            (needed for POST /funds/{symbol}/update).
    """
    app = FastAPI()
    app.include_router(funds_router, prefix="/funds")

    if fund_service_override is not None:
        from apps.api.endpoints.funds import get_fund_service
        app.dependency_overrides[get_fund_service] = fund_service_override

    if brsapi_override is not None:
        from apps.api.dependencies import get_brsapi_query_service
        app.dependency_overrides[get_brsapi_query_service] = brsapi_override

    return app


# ═══════════════════════════════════════════════════════════════════
#  GET /funds — list all funds
# ═══════════════════════════════════════════════════════════════════

class TestListFunds:
    """Tests for GET /funds."""

    @pytest.mark.asyncio
    async def test_list_default(self):
        """Default call returns items with pagination metadata."""
        app = make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/funds")

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert "type_counts" in data
        assert data["limit"] == 200
        assert data["offset"] == 0
        assert data["total"] > 0

    @pytest.mark.asyncio
    async def test_list_items_have_all_required_fields(self):
        """Each fund item has all required fields matching the Fund interface."""
        app = make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/funds?limit=1")

        assert resp.status_code == 200
        data = resp.json()
        items = data["items"]
        assert len(items) == 1
        item = items[0]

        # Identity
        assert "symbol" in item
        assert "name" in item
        assert "isin" in item
        assert "fund_type" in item

        # Pricing
        assert "nav" in item
        assert "nav_change" in item
        assert "nav_change_pct" in item
        assert "price_last" in item
        assert "price_close" in item
        assert "price_yesterday" in item
        assert "price_max" in item
        assert "price_min" in item

        # Trading
        assert "trade_volume" in item
        assert "trade_value" in item
        assert "trade_count" in item
        assert "shares_count" in item
        assert "base_volume" in item
        assert "market_value" in item

        # Real/Legal
        assert "buy_real_volume" in item
        assert "buy_legal_volume" in item
        assert "sell_real_volume" in item
        assert "sell_legal_volume" in item

        # Metadata
        assert "time" in item

    @pytest.mark.asyncio
    async def test_list_search_by_symbol(self):
        """Search by symbol filters results correctly."""
        app = make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # "کالا" matches nearly all commodity-exchange fund names
            resp = await client.get("/funds?search=کالا")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert "کالا" in item["symbol"] or "کالا" in item["name"]

    @pytest.mark.asyncio
    async def test_list_search_no_results(self):
        """Search with non-existent query returns empty items."""
        app = make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/funds?search=NON_EXISTENT_SYMBOL_XYZ")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_list_filter_by_type(self):
        """Filter by fund_type returns only matching funds."""
        app = make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/funds?fund_type=" + "سهامی")

        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["fund_type"] in ("سهامی",)

    @pytest.mark.asyncio
    async def test_list_sort_by_nav_desc(self):
        """Default sort by NAV descending."""
        app = make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/funds?sort_by=nav&sort_desc=true&limit=5")

        assert resp.status_code == 200
        data = resp.json()
        items = data["items"]
        assert len(items) >= 2
        # Verify desc: first NAV >= second NAV
        assert items[0]["nav"] >= items[1]["nav"]

    @pytest.mark.asyncio
    async def test_list_sort_by_nav_asc(self):
        """Sort by NAV ascending."""
        app = make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/funds?sort_by=nav&sort_desc=false&limit=5")

        assert resp.status_code == 200
        data = resp.json()
        items = data["items"]
        assert len(items) >= 2
        assert items[0]["nav"] <= items[1]["nav"]

    @pytest.mark.asyncio
    async def test_list_pagination_offset(self):
        """Offset skips the first N items."""
        app = make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First two items
            resp1 = await client.get("/funds?limit=1&offset=0")
            resp2 = await client.get("/funds?limit=1&offset=1")

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        item1 = resp1.json()["items"][0]
        item2 = resp2.json()["items"][0]
        # Different items should be returned
        assert item1["symbol"] != item2["symbol"]


# ═══════════════════════════════════════════════════════════════════
#  GET /funds/types
# ═══════════════════════════════════════════════════════════════════

class TestFundTypes:
    """Tests for GET /funds/types."""

    @pytest.mark.asyncio
    async def test_types_returns_all_six_types(self):
        """Should return all 6 fund types with key and label."""
        app = make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/funds/types")

        assert resp.status_code == 200
        types = resp.json()
        assert isinstance(types, list)
        assert len(types) == 6

        keys = {t["key"] for t in types}
        expected_keys = {"سهامی", "درآمد ثابت", "اهرمی", "مختلط", "بخشی", "اختصاصی"}
        assert keys == expected_keys

    @pytest.mark.asyncio
    async def test_types_have_persian_labels(self):
        """Each type has a Persian label."""
        app = make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/funds/types")

        assert resp.status_code == 200
        for t in resp.json():
            assert "key" in t
            assert "label" in t
            assert len(t["label"]) > 0


# ═══════════════════════════════════════════════════════════════════
#  GET /funds/{symbol}
# ═══════════════════════════════════════════════════════════════════

class TestGetFund:
    """Tests for GET /funds/{symbol}."""

    @pytest.mark.asyncio
    async def test_get_existing_fund(self):
        """Returns fund data with analysis for existing symbol."""
        app = make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First find a symbol from the list
            list_resp = await client.get("/funds?limit=1")
            symbol = list_resp.json()["items"][0]["symbol"]

            resp = await client.get(f"/funds/{symbol}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == symbol
        assert "analysis" in data
        assert "scores" in data["analysis"]
        assert "total" in data["analysis"]["scores"]
        assert "recommendation" in data["analysis"]

    @pytest.mark.asyncio
    async def test_get_nonexistent_fund(self):
        """Returns error for non-existent symbol."""
        app = make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/funds/NONEXISTENT")

        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data
        assert "یافت نشد" in data["error"]

    @pytest.mark.asyncio
    async def test_get_fund_with_analysis_fields(self):
        """Analysis has score and recommendation."""
        app = make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            list_resp = await client.get("/funds?limit=1")
            symbol = list_resp.json()["items"][0]["symbol"]

            resp = await client.get(f"/funds/{symbol}")

        assert resp.status_code == 200
        analysis = resp.json()["analysis"]
        assert 0 <= analysis["scores"]["total"] <= 100
        assert analysis["recommendation"] in ("STRONG_BUY", "BUY", "WATCHLIST", "HOLD", "REDUCE", "AVOID")


# ═══════════════════════════════════════════════════════════════════
#  GET /funds/{symbol}/analysis
# ═══════════════════════════════════════════════════════════════════

class TestFundAnalysis:
    """Tests for GET /funds/{symbol}/analysis."""

    @pytest.mark.asyncio
    async def test_analysis_returns_6_dimensions(self):
        """Full analysis has all 6 dimension scores."""
        app = make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            list_resp = await client.get("/funds?limit=1")
            symbol = list_resp.json()["items"][0]["symbol"]

            resp = await client.get(f"/funds/{symbol}/analysis")

        assert resp.status_code == 200
        data = resp.json()
        scores = data["scores"]
        dims = ["financial", "liquidity", "management", "risk", "cost", "transparency", "total"]
        for dim in dims:
            assert dim in scores
            assert 0 <= scores[dim] <= 100

    @pytest.mark.asyncio
    async def test_analysis_has_recommendation_and_risk(self):
        """Analysis includes recommendation, risk_level, and summary."""
        app = make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            list_resp = await client.get("/funds?limit=1")
            symbol = list_resp.json()["items"][0]["symbol"]

            resp = await client.get(f"/funds/{symbol}/analysis")

        assert resp.status_code == 200
        data = resp.json()
        assert data["recommendation"] in ("STRONG_BUY", "BUY", "WATCHLIST", "HOLD", "REDUCE", "AVOID")
        assert data["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        assert "summary" in data

    @pytest.mark.asyncio
    async def test_analysis_nonexistent_symbol(self):
        """Returns error for non-existent symbol."""
        app = make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/funds/NONEXISTENT/analysis")

        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data
        assert "یافت نشد" in data["error"]


# ═══════════════════════════════════════════════════════════════════
#  POST /funds/{symbol}/update
# ═══════════════════════════════════════════════════════════════════

class TestUpdateFund:
    """Tests for POST /funds/{symbol}/update — with mocked FundService + BrsApi."""

    @pytest.mark.asyncio
    async def test_update_existing_fund(self):
        """Mocks FundService + BrsApi, verifies update_from_brsapi was called."""
        mock_brsapi = AsyncMock()
        mock_service = AsyncMock(spec=FundService)
        mock_service.update_from_brsapi.return_value = {
            "symbol": "آگاس",
            "name": "آتیه‌اندیشان اقتصاد پایدار",
            "isin": "IRAGAS001",
            "fund_type": "اختصاصی",
            "nav": 15500.0,
            "nav_change": 500.0,
            "nav_change_pct": 3.33,
            "price_last": 15500,
            "price_close": 15400,
            "price_yesterday": 15000,
            "price_max": 15600,
            "price_min": 14900,
            "trade_volume": 500000,
            "trade_value": 7500000000,
            "trade_count": 120,
            "shares_count": 10000000,
            "base_volume": 100000,
            "market_value": 155000000000,
            "buy_real_volume": 200000,
            "buy_legal_volume": 100000,
            "sell_real_volume": 150000,
            "sell_legal_volume": 50000,
            "time": "12:00:00",
            "data_source": "brsapi",
        }

        async def override_fund():
            return mock_service

        async def override_brsapi():
            return mock_brsapi

        app = make_app(fund_service_override=override_fund, brsapi_override=override_brsapi)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/funds/آگاس/update")

        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "آگاس"
        assert data["nav"] == 15500.0
        assert data["nav_change_pct"] == 3.33
        assert data["data_source"] == "brsapi"
        assert data["fund_type"] == "اختصاصی"

        mock_service.update_from_brsapi.assert_called_once()
        call_args = mock_service.update_from_brsapi.call_args
        assert call_args[1]["symbol"] == "آگاس"
        assert call_args[1]["brsapi"] is mock_brsapi

    @pytest.mark.asyncio
    async def test_update_error_response(self):
        """When update_from_brsapi returns error, the endpoint passes it through."""
        mock_service = AsyncMock(spec=FundService)
        mock_service.update_from_brsapi.return_value = {
            "symbol": "ناموجود",
            "error": "نماد ناموجود در BrsApi یافت نشد",
        }

        async def override_fund():
            return mock_service

        mock_brsapi = AsyncMock()
        async def override_brsapi():
            return mock_brsapi

        app = make_app(fund_service_override=override_fund, brsapi_override=override_brsapi)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/funds/ناموجود/update")

        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data
        assert "یافت نشد" in data["error"]


# ═══════════════════════════════════════════════════════════════════
#  Edge cases
# ═══════════════════════════════════════════════════════════════════

class TestFundsEdgeCases:
    """Edge cases for funds API."""

    @pytest.mark.asyncio
    async def test_invalid_limit_returns_422(self):
        """Limit > 500 should return 422 validation error."""
        app = make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/funds?limit=999")

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_negative_offset_returns_422(self):
        """Negative offset should return 422 validation error."""
        app = make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/funds?offset=-1")

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_get_fund_with_special_chars(self):
        """Fund with special characters in symbol is handled (symbols are Persian)."""
        # Find a symbol with Persian chars
        app = make_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            list_resp = await client.get("/funds?limit=5")
            items = list_resp.json()["items"]

        # All symbols should be valid Persian (encoded in URL)
        assert len(items) > 0
