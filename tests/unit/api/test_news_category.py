"""Regression tests for the news category contract.

Covers the ``company``/``companies`` mismatch fixed in this commit:

* The ingestion classifier (``services/news_ingestion.py``) has always stored
  the plural ``companies`` while ``apps.api.endpoints.news.VALID_CATEGORIES``
  only accepted the singular ``company`` — so ``GET /news/category/companies``
  (the value the frontend tab and the RSS pipeline both use) was rejected with
  400, and ``GET /news/category/company`` passed but never matched any stored
  item. The endpoint list now contains the canonical plural, and the legacy
  singular plus the news-module spec's ``stock_market`` are accepted as
  aliases, normalized before comparison.

The endpoint logic is exercised through the real router functions with a
stubbed ``NewsService`` — no DB, no HTTP server.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from apps.api.endpoints import news as news_endpoint
from apps.api.endpoints.news import (
    VALID_CATEGORIES,
    list_news,
    news_by_category,
    normalize_news_category,
)
from core.result import PaginatedResult, Result
from domain.news.news_item import NewsItem


def _news_item(category: str, news_id: str = "news_1") -> NewsItem:
    return NewsItem(
        id=news_id,
        title=f"title {news_id}",
        summary="sum",
        source="rss",
        url=f"https://example.test/{news_id}",
        publish_date=datetime(2026, 9, 16, 10, 0, tzinfo=UTC),
        category=category,
    )


def _paginated(items: list[NewsItem], page_size: int = 50) -> PaginatedResult[NewsItem]:
    return PaginatedResult(items=items, total=len(items), page=1, page_size=page_size, total_pages=1)


def _stub_service(items: list[NewsItem]) -> AsyncMock:
    service = AsyncMock()
    service.list_all.return_value = Result.ok(_paginated(items))
    return service


class TestValidCategoriesContract:
    """The config contract: canonical plural present, aliases accepted."""

    def test_plural_companies_is_valid(self):
        # The exact regression: the ingestion pipeline and the frontend tab
        # both use ``companies`` — it must not 400 anymore.
        assert "companies" in VALID_CATEGORIES

    def test_all_canonical_categories_present(self):
        assert {"market", "companies", "economic", "political", "international"} <= VALID_CATEGORIES

    def test_aliases_accepted(self):
        assert "company" in VALID_CATEGORIES
        assert "stock_market" in VALID_CATEGORIES

    def test_unknown_category_rejected(self):
        assert "nosuchcat" not in VALID_CATEGORIES


class TestCategoryAliases:
    """normalize_news_category mapping."""

    def test_company_maps_to_companies(self):
        assert normalize_news_category("company") == "companies"

    def test_stock_market_maps_to_market(self):
        assert normalize_news_category("stock_market") == "market"

    def test_canonical_values_pass_through(self):
        for cat in ("market", "companies", "economic", "political", "international"):
            assert normalize_news_category(cat) == cat

    def test_unknown_value_passes_through(self):
        assert normalize_news_category("weird") == "weird"


class TestListNewsCategoryFilter:
    """``GET /news?category=...`` matches stored items through aliases."""

    @pytest.mark.asyncio
    async def test_companies_filter_matches_stored_companies(self):
        items = [
            _news_item("companies", "n1"),
            _news_item("market", "n2"),
            _news_item("economic", "n3"),
        ]
        result = await list_news(
            page=1,
            page_size=50,
            category="companies",
            service=_stub_service(items),
            session=AsyncMock(),
        )
        returned = result.data.items
        assert [i.id for i in returned] == ["n1"]

    @pytest.mark.asyncio
    async def test_legacy_company_alias_matches_stored_companies(self):
        # Before the fix this filter never matched anything.
        items = [_news_item("companies", "n1"), _news_item("market", "n2")]
        result = await list_news(
            page=1,
            page_size=50,
            category="company",
            service=_stub_service(items),
            session=AsyncMock(),
        )
        returned = result.data.items
        assert [i.id for i in returned] == ["n1"]

    @pytest.mark.asyncio
    async def test_stock_market_alias_matches_stored_market(self):
        items = [_news_item("market", "n1"), _news_item("companies", "n2")]
        result = await list_news(
            page=1,
            page_size=50,
            category="stock_market",
            service=_stub_service(items),
            session=AsyncMock(),
        )
        returned = result.data.items
        assert [i.id for i in returned] == ["n1"]


class TestNewsByCategoryEndpoint:
    """``GET /news/category/{category}`` validation + alias routing."""

    @pytest.mark.asyncio
    async def test_companies_is_accepted(self):
        # Exact regression of the 400 the frontend received.
        items = [_news_item("companies", "n1")]
        result = await news_by_category(
            category="companies",
            page=1,
            service=_stub_service(items),
            session=AsyncMock(),
        )
        assert result.success is True
        assert [i.id for i in result.data] == ["n1"]

    @pytest.mark.asyncio
    async def test_legacy_company_accepted_and_matches_companies(self):
        items = [_news_item("companies", "n1")]
        result = await news_by_category(
            category="company",
            page=1,
            service=_stub_service(items),
            session=AsyncMock(),
        )
        assert result.success is True
        assert [i.id for i in result.data] == ["n1"]

    @pytest.mark.asyncio
    async def test_stock_market_accepted_and_matches_market(self):
        items = [_news_item("market", "n1")]
        result = await news_by_category(
            category="stock_market",
            page=1,
            service=_stub_service(items),
            session=AsyncMock(),
        )
        assert result.success is True
        assert [i.id for i in result.data] == ["n1"]

    @pytest.mark.asyncio
    async def test_invalid_category_returns_error(self):
        result = await news_by_category(
            category="not-a-category",
            page=1,
            service=AsyncMock(),
            session=AsyncMock(),
        )
        assert result.success is False
        assert result.error is not None and "Invalid category" in result.error["message"]
        # Error message must advertise the canonical plural.
        assert "companies" in result.error["message"]


class TestIngestionAliasNormalization:
    """The ingestion-side classifier normalizes aliases before keyword matching."""

    def test_raw_stock_market_becomes_market_without_keyword_hit(self):
        # An exact raw category must not depend on Persian keywords scoring.
        assert news_endpoint  # module loaded; real assertion below
        from services.news_ingestion import _classify_category

        assert _classify_category("stock_market") == "market"

    def test_raw_company_becomes_companies(self):
        from services.news_ingestion import _classify_category

        assert _classify_category("company") == "companies"

    def test_exact_companies_raw_category_survives(self):
        from services.news_ingestion import _classify_category

        assert _classify_category("companies") == "companies"

    def test_alias_normalized_even_with_noisy_title(self):
        from services.news_ingestion import _classify_category

        # Title contains political keywords that must not override the
        # normalized explicit category… (keyword scoring may still win, but
        # normalization must have replaced the alias itself).
        result = _classify_category("stock_market", title="سیاست دولت مجلس")
        assert result in {"market", "political"}
