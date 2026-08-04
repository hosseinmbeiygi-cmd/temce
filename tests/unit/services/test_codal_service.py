"""Unit tests for CodalService.

Covers:
  - list_all: paginated disclosure listing
  - get_by_instrument: instrument-specific disclosures
  - create: new disclosure creation
  - save: existing disclosure update
  - Error handling and edge cases
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.result import PaginatedResult, Result
from domain.codal.disclosure import Disclosure
from services.codal_service import CodalService

# ── Helpers ──────────────────────────────────────────────────────


def _make_service(**kwargs: Any) -> CodalService:
    """Create a CodalService with all dependencies mocked."""
    defaults: dict[str, Any] = {"repo": MagicMock(), "session": MagicMock()}
    defaults.update(kwargs)
    return CodalService(**defaults)


def _make_disclosure(**overrides: Any) -> Disclosure:
    """Create a mock Disclosure with default values."""
    defaults = {
        "id": "cod_001",
        "instrument_id": "inst_001",
        "title": "گزارش مالی سالانه",
        "publish_date": "2024-01-15",
        "category": "financial",
        "sent_to_codal": True,
    }
    defaults.update(overrides)
    return MagicMock(**defaults)


# ════════════════════════════════════════════════════════════════
# 1. list_all
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestListAll:
    async def test_returns_paginated_disclosures(self):
        svc = _make_service()
        items = [_make_disclosure(), _make_disclosure(id="cod_002")]
        mock_result = PaginatedResult(items=items, total=2, page=1, page_size=50, total_pages=1)
        svc.repo.list = AsyncMock(return_value=Result.ok(mock_result))

        result = await svc.list_all()
        assert result.success
        assert result.value.total == 2
        assert len(result.value.items) == 2

    async def test_empty_list(self):
        svc = _make_service()
        mock_result = PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=0)
        svc.repo.list = AsyncMock(return_value=Result.ok(mock_result))

        result = await svc.list_all()
        assert result.success
        assert result.value.total == 0

    async def test_repo_failure(self):
        svc = _make_service()
        svc.repo.list = AsyncMock(return_value=Result.fail("Database timeout"))

        result = await svc.list_all()
        assert not result.success
        assert "Database timeout" in result.error

    async def test_pagination_params(self):
        svc = _make_service()
        mock_result = PaginatedResult(items=[], total=100, page=3, page_size=10, total_pages=10)
        svc.repo.list = AsyncMock(return_value=Result.ok(mock_result))

        result = await svc.list_all(page=3, page_size=10)
        assert result.success
        assert result.value.page == 3
        assert result.value.page_size == 10

    async def test_delegates_to_repo(self):
        svc = _make_service()
        svc.repo.list = AsyncMock(return_value=Result.ok(PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=0)))

        await svc.list_all(page=5, page_size=25)
        svc.repo.list.assert_called_once_with(5, 25)


# ════════════════════════════════════════════════════════════════
# 2. get_by_instrument
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestGetByInstrument:
    async def test_found(self):
        svc = _make_service()
        items = [_make_disclosure(instrument_id="inst_001")]
        mock_result = PaginatedResult(items=items, total=1, page=1, page_size=50, total_pages=1)
        svc.repo.get_by_instrument = AsyncMock(return_value=Result.ok(mock_result))

        result = await svc.get_by_instrument("inst_001")
        assert result.success
        assert result.value.total == 1

    async def test_not_found(self):
        svc = _make_service()
        mock_result = PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=0)
        svc.repo.get_by_instrument = AsyncMock(return_value=Result.ok(mock_result))

        result = await svc.get_by_instrument("nonexistent_instrument")
        assert result.success
        assert result.value.total == 0

    async def test_delegates_to_repo(self):
        svc = _make_service()
        svc.repo.get_by_instrument = AsyncMock(return_value=Result.ok(PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=0)))

        await svc.get_by_instrument("inst_002", page=2, page_size=20)
        svc.repo.get_by_instrument.assert_called_once_with("inst_002", 2, 20)


# ════════════════════════════════════════════════════════════════
# 3. create
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestCreate:
    async def test_creates_new_disclosure(self):
        svc = _make_service()
        saved = _make_disclosure()
        svc.repo.save = AsyncMock(return_value=Result.ok(saved))

        result = await svc.create("inst_001", "گزارش جدید", category="financial")
        assert result.success
        svc.repo.save.assert_called_once()

    async def test_create_generates_id(self):
        svc = _make_service()
        svc.repo.save = AsyncMock(return_value=Result.ok(_make_disclosure()))

        await svc.create("inst_001", "Title")
        call_args = svc.repo.save.call_args
        disclosure = call_args[0][0]
        assert disclosure.id.startswith("cod_")

    async def test_create_with_kwargs(self):
        svc = _make_service()
        svc.repo.save = AsyncMock(return_value=Result.ok(_make_disclosure()))

        await svc.create("inst_001", "Title", category="audit", disclosure_type="financial")
        call_args = svc.repo.save.call_args
        disclosure = call_args[0][0]
        assert disclosure.category == "audit"
        assert disclosure.disclosure_type == "financial"


# ════════════════════════════════════════════════════════════════
# 4. save
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestSave:
    async def test_saves_existing_disclosure(self):
        svc = _make_service()
        disc = _make_disclosure()
        svc.repo.save = AsyncMock(return_value=Result.ok(disc))

        result = await svc.save(disc)
        assert result.success
        svc.repo.save.assert_called_once_with(disc)

    async def test_save_failure(self):
        svc = _make_service()
        svc.repo.save = AsyncMock(return_value=Result.fail("Unique constraint violated"))

        disc = _make_disclosure()
        result = await svc.save(disc)
        assert not result.success
        assert "Unique constraint violated" in result.error


# ════════════════════════════════════════════════════════════════
# 5. Edge cases
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestEdgeCases:
    async def test_get_by_instrument_empty_id(self):
        svc = _make_service()
        mock_result = PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=0)
        svc.repo.get_by_instrument = AsyncMock(return_value=Result.ok(mock_result))

        result = await svc.get_by_instrument("")
        assert result.success

    async def test_create_empty_title(self):
        svc = _make_service()
        svc.repo.save = AsyncMock(return_value=Result.ok(_make_disclosure()))

        result = await svc.create("inst_001", "")
        assert result.success  # Service doesn't validate title

    async def test_list_all_large_page(self):
        svc = _make_service()
        mock_result = PaginatedResult(items=[], total=1000, page=100, page_size=10, total_pages=100)
        svc.repo.list = AsyncMock(return_value=Result.ok(mock_result))

        result = await svc.list_all(page=100, page_size=10)
        assert result.success
        assert result.value.total == 1000
