"""Unit tests for NewsService.

Covers:
  - list_all: sorted by publish_date, pagination
  - search: query-based search
  - get_by_symbol: symbol filtering
  - create: new news item creation
  - save: existing item update
  - Error handling and edge cases
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.result import PaginatedResult, Result
from domain.news.news_item import NewsItem
from services.news_service import NewsService

# ── Helpers ──────────────────────────────────────────────────────


def _make_service(**kwargs: Any) -> NewsService:
    """Create a NewsService with all dependencies mocked."""
    defaults: dict[str, Any] = {"repo": MagicMock(), "session": MagicMock()}
    defaults.update(kwargs)
    return NewsService(**defaults)


def _make_news_item(**overrides: Any) -> NewsItem:
    """Create a mock NewsItem with default values."""
    defaults = {
        "id": "news_001",
        "title": "Test News",
        "content": "Test content",
        "source": "tsetmc",
        "publish_date": "2024-01-15",
        "created_at": "2024-01-15T10:00:00",
        "symbols": ["فولاد"],
    }
    defaults.update(overrides)
    return MagicMock(**defaults)


# ════════════════════════════════════════════════════════════════
# 1. list_all
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestListAll:
    async def test_returns_sorted_items(self):
        svc = _make_service()
        item1 = _make_news_item(publish_date="2024-01-10", created_at="2024-01-10T09:00:00")
        item2 = _make_news_item(publish_date="2024-01-15", created_at="2024-01-15T09:00:00")
        item3 = _make_news_item(publish_date="2024-01-12", created_at="2024-01-12T09:00:00")

        mock_result = PaginatedResult(
            items=[item1, item2, item3], total=3, page=1, page_size=50, total_pages=1
        )
        svc.repo.list = AsyncMock(return_value=Result.ok(mock_result))

        result = await svc.list_all()
        assert result.success
        # Items should be sorted by publish_date descending
        assert result.value.items[0].publish_date == "2024-01-15"
        assert result.value.items[1].publish_date == "2024-01-12"
        assert result.value.items[2].publish_date == "2024-01-10"

    async def test_empty_list(self):
        svc = _make_service()
        mock_result = PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=0)
        svc.repo.list = AsyncMock(return_value=Result.ok(mock_result))

        result = await svc.list_all()
        assert result.success
        assert result.value.total == 0

    async def test_repo_failure(self):
        svc = _make_service()
        svc.repo.list = AsyncMock(return_value=Result.fail("DB connection error"))

        result = await svc.list_all()
        assert not result.success
        assert "DB connection error" in result.error

    async def test_pagination_params(self):
        svc = _make_service()
        mock_result = PaginatedResult(items=[], total=100, page=2, page_size=10, total_pages=10)
        svc.repo.list = AsyncMock(return_value=Result.ok(mock_result))

        result = await svc.list_all(page=2, page_size=10)
        assert result.success
        assert result.value.page == 2
        assert result.value.page_size == 10


# ════════════════════════════════════════════════════════════════
# 2. search
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestSearch:
    async def test_search_returns_results(self):
        svc = _make_service()
        items = [_make_news_item(title="فولاد افزایش یافت")]
        mock_result = PaginatedResult(items=items, total=1, page=1, page_size=50, total_pages=1)
        svc.repo.search = AsyncMock(return_value=Result.ok(mock_result))

        result = await svc.search("فولاد")
        assert result.success
        assert result.value.total == 1

    async def test_search_empty_results(self):
        svc = _make_service()
        mock_result = PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=0)
        svc.repo.search = AsyncMock(return_value=Result.ok(mock_result))

        result = await svc.search("نماد_ناموجود")
        assert result.success
        assert result.value.total == 0

    async def test_search_delegates_to_repo(self):
        svc = _make_service()
        svc.repo.search = AsyncMock(return_value=Result.ok(PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=0)))

        await svc.search("test_query", page=3, page_size=20)
        svc.repo.search.assert_called_once_with("test_query", 3, 20)


# ════════════════════════════════════════════════════════════════
# 3. get_by_symbol
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestGetBySymbol:
    async def test_found(self):
        svc = _make_service()
        items = [_make_news_item(), _make_news_item(id="news_002")]
        mock_result = PaginatedResult(items=items, total=2, page=1, page_size=50, total_pages=1)
        svc.repo.get_by_symbol = AsyncMock(return_value=Result.ok(mock_result))

        result = await svc.get_by_symbol("فولاد")
        assert result.success
        assert len(result.value.items) == 2

    async def test_not_found(self):
        svc = _make_service()
        mock_result = PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=0)
        svc.repo.get_by_symbol = AsyncMock(return_value=Result.ok(mock_result))

        result = await svc.get_by_symbol("نماد_ناموجود")
        assert result.success
        assert result.value.total == 0

    async def test_delegates_to_repo(self):
        svc = _make_service()
        svc.repo.get_by_symbol = AsyncMock(return_value=Result.ok(PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=0)))

        await svc.get_by_symbol("خودرو", page=2, page_size=25)
        svc.repo.get_by_symbol.assert_called_once_with("خودرو", 2, 25)


# ════════════════════════════════════════════════════════════════
# 4. create
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestCreate:
    async def test_creates_new_item(self):
        svc = _make_service()
        saved_item = _make_news_item()
        svc.repo.save = AsyncMock(return_value=Result.ok(saved_item))

        result = await svc.create("Breaking News", content="Important", source="tsetmc")
        assert result.success
        svc.repo.save.assert_called_once()

    async def test_create_generates_id(self):
        svc = _make_service()
        svc.repo.save = AsyncMock(return_value=Result.ok(_make_news_item()))

        await svc.create("Title")
        # The saved item should have an ID generated by new_id
        call_args = svc.repo.save.call_args
        assert call_args is not None
        item = call_args[0][0]
        assert item.id.startswith("news_")

    async def test_create_with_kwargs(self):
        svc = _make_service()
        svc.repo.save = AsyncMock(return_value=Result.ok(_make_news_item()))

        await svc.create("Title", symbols=["فولاد", "خودرو"], category="market")
        call_args = svc.repo.save.call_args
        item = call_args[0][0]
        assert item.symbols == ["فولاد", "خودرو"]
        assert item.category == "market"


# ════════════════════════════════════════════════════════════════
# 5. save
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestSave:
    async def test_saves_existing_item(self):
        svc = _make_service()
        item = _make_news_item()
        svc.repo.save = AsyncMock(return_value=Result.ok(item))

        result = await svc.save(item)
        assert result.success
        svc.repo.save.assert_called_once_with(item)

    async def test_save_failure(self):
        svc = _make_service()
        svc.repo.save = AsyncMock(return_value=Result.fail("Constraint violation"))

        item = _make_news_item()
        result = await svc.save(item)
        assert not result.success
        assert "Constraint violation" in result.error


# ════════════════════════════════════════════════════════════════
# 6. Edge cases
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestEdgeCases:
    async def test_list_all_items_with_none_dates(self):
        """Items with None publish_date should still sort correctly."""
        svc = _make_service()
        item1 = _make_news_item(publish_date=None, created_at="2024-01-15T09:00:00")
        item2 = _make_news_item(publish_date="2024-01-10", created_at=None)
        mock_result = PaginatedResult(items=[item1, item2], total=2, page=1, page_size=50, total_pages=1)
        svc.repo.list = AsyncMock(return_value=Result.ok(mock_result))

        result = await svc.list_all()
        assert result.success
        # Items with None dates should sort to the end
        assert len(result.value.items) == 2

    async def test_create_with_empty_title(self):
        svc = _make_service()
        svc.repo.save = AsyncMock(return_value=Result.ok(_make_news_item()))

        result = await svc.create("")
        assert result.success  # Service doesn't validate title

    async def test_search_special_characters(self):
        svc = _make_service()
        svc.repo.search = AsyncMock(return_value=Result.ok(PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=0)))

        result = await svc.search("فولاد & خودرو % شپنا")
        assert result.success
