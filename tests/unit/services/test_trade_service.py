"""Unit tests for TradeService.

Covers:
  - get_trades: fetch trades with DB fallback to live API
  - get_recent: recent trades with live fallback
  - save_trade: persist single trade record
  - _fetch_live_trades: live API fetch with persistence
  - Error handling and edge cases
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.trade_service import TradeService

# ── Helpers ──────────────────────────────────────────────────────


def _make_service(**kwargs: Any) -> TradeService:
    """Create a TradeService with mocked dependencies."""
    defaults: dict[str, Any] = {
        "brsapi_query_service": MagicMock(),
        "brsapi_client": MagicMock(),
    }
    defaults.update(kwargs)
    return TradeService(**defaults)


def _make_trade(**overrides: Any) -> dict[str, Any]:
    """Create a mock trade record with default values."""
    defaults = {
        "id": "trade_001",
        "symbol": "فولاد",
        "trade_date": "2024-01-15",
        "trade_time": "10:30:00",
        "price": 5000,
        "volume": 1000,
        "value": 5000000,
        "side": "buy",
    }
    defaults.update(overrides)
    return defaults


# ════════════════════════════════════════════════════════════════
# 1. get_trades
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestGetTrades:
    async def test_returns_trades_from_db(self):
        svc = _make_service()
        trades = [_make_trade(), _make_trade(id="trade_002")]
        svc._brsapi.get_intraday_trades = AsyncMock(return_value=trades)

        result = await svc.get_trades("فولاد")
        assert result.success
        assert len(result.value) == 2

    async def test_falls_back_to_live_api(self):
        svc = _make_service()
        svc._brsapi.get_intraday_trades = AsyncMock(return_value=[])

        with patch.object(svc, "_fetch_live_trades", new_callable=AsyncMock, return_value=[_make_trade()]):
            result = await svc.get_trades("فولاد")
            assert result.success
            assert len(result.value) == 1

    async def test_returns_empty_when_no_sources(self):
        svc = _make_service(brsapi_client=None)
        svc._brsapi.get_intraday_trades = AsyncMock(return_value=[])

        result = await svc.get_trades("فولاد")
        assert result.success
        assert result.value == []

    async def test_db_failure_returns_empty(self):
        svc = _make_service(brsapi_client=None)
        svc._brsapi.get_intraday_trades = AsyncMock(side_effect=Exception("DB error"))

        result = await svc.get_trades("فولاد")
        assert result.success
        assert result.value == []

    async def test_custom_limit(self):
        svc = _make_service()
        trades = [_make_trade() for _ in range(50)]
        svc._brsapi.get_intraday_trades = AsyncMock(return_value=trades)

        result = await svc.get_trades("فولاد", limit=50)
        assert result.success
        assert len(result.value) == 50


# ════════════════════════════════════════════════════════════════
# 2. get_recent
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestGetRecent:
    async def test_returns_recent_trades(self):
        svc = _make_service()
        trades = [_make_trade(), _make_trade(id="trade_002")]
        svc._brsapi.get_intraday_trades = AsyncMock(return_value=trades)

        result = await svc.get_recent("فولاد")
        assert result.success
        assert len(result.value) == 2

    async def test_falls_back_to_live(self):
        svc = _make_service()
        svc._brsapi.get_intraday_trades = AsyncMock(return_value=[])

        with patch.object(svc, "_fetch_live_trades", new_callable=AsyncMock, return_value=[_make_trade()]):
            result = await svc.get_recent("فولاد")
            assert result.success
            assert len(result.value) == 1

    async def test_returns_empty_when_no_sources(self):
        svc = _make_service(brsapi_client=None)
        svc._brsapi.get_intraday_trades = AsyncMock(return_value=[])

        result = await svc.get_recent("فولاد")
        assert result.success
        assert result.value == []

    async def test_failure_returns_empty(self):
        svc = _make_service(brsapi_client=None)
        svc._brsapi.get_intraday_trades = AsyncMock(side_effect=Exception("DB error"))

        result = await svc.get_recent("فولاد")
        assert result.success
        assert result.value == []


# ════════════════════════════════════════════════════════════════
# 3. save_trade
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestSaveTrade:
    async def test_saves_trade(self):
        svc = _make_service()
        data = _make_trade()

        # save_trade does: async for session in get_session()
        # get_session is an async generator, so mock it as an async generator
        mock_session = AsyncMock()

        async def mock_get_session():
            yield mock_session

        mock_repo = MagicMock()
        mock_repo.bulk_insert = AsyncMock()

        with patch("core.database.get_session", side_effect=mock_get_session), \
             patch("brsapi.repositories.BulkUpsertRepository", return_value=mock_repo):
            result = await svc.save_trade(data)
            assert result.success
            mock_repo.bulk_insert.assert_called_once_with([data])

    async def test_save_failure(self):
        svc = _make_service()
        data = _make_trade()

        async def failing_gen():
            raise Exception("DB error")
            yield  # make it an async generator

        with patch("core.database.get_session", side_effect=failing_gen):
            result = await svc.save_trade(data)
            assert not result.success
            assert "DB error" in result.error


# ════════════════════════════════════════════════════════════════
# 4. _fetch_live_trades
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestFetchLiveTrades:
    async def test_fetches_and_saves(self):
        svc = _make_service()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.value = MagicMock()
        mock_result.value.data = [{"time": "10:30:00", "price": 5000, "volume": 1000}]
        svc._client.fetch = AsyncMock(return_value=mock_result)

        mock_parser = MagicMock()
        mock_parser.parse_transactions = MagicMock(return_value=[{"price": 5000}])

        with patch("brsapi.parsers.TsetmcParser", mock_parser), \
             patch.object(svc, "_save_live_trades", new_callable=AsyncMock):
            result = await svc._fetch_live_trades("فولاد", 10)
            assert len(result) == 1
            assert result[0]["symbol"] == "فولاد"

    async def test_fetch_failure(self):
        svc = _make_service()
        svc._client.fetch = AsyncMock(side_effect=Exception("API error"))

        result = await svc._fetch_live_trades("فولاد", 10)
        assert result == []

    async def test_fetch_empty_response(self):
        svc = _make_service()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.value = MagicMock()
        mock_result.value.data = []
        svc._client.fetch = AsyncMock(return_value=mock_result)

        mock_parser = MagicMock()
        mock_parser.parse_transactions = MagicMock(return_value=[])

        with patch("brsapi.parsers.TsetmcParser", mock_parser):
            result = await svc._fetch_live_trades("فولاد", 10)
            assert result == []


# ════════════════════════════════════════════════════════════════
# 5. Edge cases
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestEdgeCases:
    async def test_get_trades_with_limit_1(self):
        svc = _make_service()
        trades = [_make_trade()]
        svc._brsapi.get_intraday_trades = AsyncMock(return_value=trades)

        result = await svc.get_trades("فولاد", limit=1)
        assert result.success
        assert len(result.value) == 1

    async def test_get_recent_with_no_data(self):
        svc = _make_service()
        svc._brsapi.get_intraday_trades = AsyncMock(return_value=[])

        result = await svc.get_recent("نماد_ناموجود")
        assert result.success
        assert result.value == []

    async def test_save_trade_with_missing_fields(self):
        svc = _make_service()
        data = {"symbol": "فولاد"}

        mock_session = AsyncMock()

        async def mock_get_session():
            yield mock_session

        mock_repo = MagicMock()
        mock_repo.bulk_insert = AsyncMock()

        with patch("core.database.get_session", side_effect=mock_get_session), \
             patch("brsapi.repositories.BulkUpsertRepository", return_value=mock_repo):
            result = await svc.save_trade(data)
            assert result.success
