"""Unit tests for PortfolioService.

Covers:
  - get_portfolio: portfolio with positions
  - list_portfolios: simplified portfolio list
  - create_portfolio: new portfolio creation
  - Error handling and edge cases
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.result import Result
from services.portfolio_service import PortfolioService

# ── Helpers ──────────────────────────────────────────────────────


def _make_service(**kwargs: Any) -> PortfolioService:
    """Create a PortfolioService with mocked repo."""
    session = AsyncMock()
    svc = PortfolioService(session=session)
    svc.repo = MagicMock()
    return svc


def _make_portfolio(**overrides: Any) -> MagicMock:
    """Create a mock Portfolio entity with explicit attribute setting."""
    p = MagicMock()
    p.id = overrides.get("id", "port_001")
    p.name = overrides.get("name", "پرتفوی آزمایشی")
    p.description = overrides.get("description", "توضیحات")
    p.initial_capital = overrides.get("initial_capital", 100_000_000.0)
    p.current_capital = overrides.get("current_capital", 105_000_000.0)
    p.currency = overrides.get("currency", "IRR")
    return p


# ════════════════════════════════════════════════════════════════
# 1. get_portfolio
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestGetPortfolio:
    async def test_returns_portfolio_with_positions(self):
        svc = _make_service()
        portfolio = _make_portfolio()
        positions = [
            {"symbol": "فولاد", "quantity": 1000, "avg_price": 5000},
            {"symbol": "خودرو", "quantity": 2000, "avg_price": 3000},
        ]
        svc.repo.get = AsyncMock(return_value=Result.ok(portfolio))
        svc.repo.get_positions = AsyncMock(return_value=Result.ok(positions))

        result = await svc.get_portfolio("port_001")
        assert result.success
        assert result.value["id"] == "port_001"
        assert result.value["name"] == "پرتفوی آزمایشی"
        assert result.value["initial_capital"] == 100_000_000.0
        assert result.value["current_value"] == 105_000_000.0
        assert result.value["currency"] == "IRR"
        assert len(result.value["positions"]) == 2

    async def test_portfolio_not_found(self):
        svc = _make_service()
        svc.repo.get = AsyncMock(return_value=Result.fail("Portfolio not found"))

        result = await svc.get_portfolio("nonexistent")
        assert not result.success

    async def test_portfolio_with_empty_positions(self):
        svc = _make_service()
        portfolio = _make_portfolio()
        svc.repo.get = AsyncMock(return_value=Result.ok(portfolio))
        svc.repo.get_positions = AsyncMock(return_value=Result.ok([]))

        result = await svc.get_portfolio("port_001")
        assert result.success
        assert result.value["positions"] == []

    async def test_positions_repo_failure(self):
        svc = _make_service()
        portfolio = _make_portfolio()
        svc.repo.get = AsyncMock(return_value=Result.ok(portfolio))
        svc.repo.get_positions = AsyncMock(return_value=Result.fail("DB error"))

        result = await svc.get_portfolio("port_001")
        # Should still succeed with empty positions
        assert result.success
        assert result.value["positions"] == []


# ════════════════════════════════════════════════════════════════
# 2. list_portfolios
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestListPortfolios:
    async def test_returns_simplified_list(self):
        svc = _make_service()
        portfolios = [
            _make_portfolio(id="port_001", name="پرتفوی ۱", current_capital=100_000_000),
            _make_portfolio(id="port_002", name="پرتفوی ۲", current_capital=200_000_000),
        ]
        mock_result = MagicMock(items=portfolios, total=2)
        svc.repo.list = AsyncMock(return_value=Result.ok(mock_result))

        result = await svc.list_portfolios()
        assert result.success
        assert len(result.value) == 2
        assert result.value[0]["id"] == "port_001"
        assert result.value[0]["name"] == "پرتفوی ۱"
        assert result.value[0]["current_value"] == 100_000_000

    async def test_empty_list(self):
        svc = _make_service()
        mock_result = MagicMock(items=[], total=0)
        svc.repo.list = AsyncMock(return_value=Result.ok(mock_result))

        result = await svc.list_portfolios()
        assert result.success
        assert result.value == []

    async def test_repo_failure(self):
        svc = _make_service()
        svc.repo.list = AsyncMock(return_value=Result.fail("DB connection error"))

        result = await svc.list_portfolios()
        assert not result.success


# ════════════════════════════════════════════════════════════════
# 3. create_portfolio
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestCreatePortfolio:
    async def test_creates_portfolio(self):
        svc = _make_service()
        saved = _make_portfolio()
        svc.repo.save = AsyncMock(return_value=Result.ok(saved))

        result = await svc.create_portfolio("پرتفوی جدید")
        assert result.success
        assert result.value["name"] == "پرتفوی جدید"
        svc.repo.save.assert_called_once()

    async def test_create_generates_id(self):
        svc = _make_service()
        svc.repo.save = AsyncMock(return_value=Result.ok(_make_portfolio()))

        await svc.create_portfolio("Test")
        call_args = svc.repo.save.call_args
        portfolio = call_args[0][0]
        assert portfolio.id.startswith("port_")

    async def test_create_failure(self):
        svc = _make_service()
        svc.repo.save = AsyncMock(return_value=Result.fail("Constraint violation"))

        result = await svc.create_portfolio("Test")
        assert not result.success
        assert "Constraint violation" in result.error


# ════════════════════════════════════════════════════════════════
# 4. Edge cases
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestEdgeCases:
    async def test_get_portfolio_repo_failure(self):
        svc = _make_service()
        svc.repo.get = AsyncMock(return_value=Result.fail("DB timeout"))

        result = await svc.get_portfolio("port_001")
        assert not result.success

    async def test_list_portfolios_with_many_items(self):
        svc = _make_service()
        portfolios = [_make_portfolio(id=f"port_{i:03d}", name=f"پرتفوی {i}") for i in range(50)]
        mock_result = MagicMock(items=portfolios, total=50)
        svc.repo.list = AsyncMock(return_value=Result.ok(mock_result))

        result = await svc.list_portfolios()
        assert result.success
        assert len(result.value) == 50
