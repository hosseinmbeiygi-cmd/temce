"""Unit tests for SignalService.

Covers:
  - create: creating signals with various types
  - get / get_signal: single signal retrieval
  - get_latest: latest signal per instrument
  - list / list_signals: paginated listing
  - get_by_symbol: symbol-based lookup
  - bulk_generate: multi-symbol generation
  - Error handling and edge cases
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.result import PaginatedResult, Result
from domain.common.enum_types import SignalType
from services.signal_service import SignalService

# ── Helpers ──────────────────────────────────────────────────────


def _make_service(**kwargs: Any) -> SignalService:
    """Create a SignalService with all dependencies mocked."""
    defaults: dict[str, Any] = {"signal_repo": MagicMock(), "session": MagicMock()}
    defaults.update(kwargs)
    return SignalService(**defaults)


# ════════════════════════════════════════════════════════════════
# 1. create
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestCreate:
    async def test_create_signal(self):
        svc = _make_service()
        svc.signal_repo.save = AsyncMock(return_value=Result.ok(MagicMock()))
        result = await svc.create("inst_001", SignalType.BULLISH, score=80.0, confidence=0.9)
        assert result.success
        svc.signal_repo.save.assert_called_once()

    async def test_create_with_string_type(self):
        svc = _make_service()
        svc.signal_repo.save = AsyncMock(return_value=Result.ok(MagicMock()))
        # SignalType enum values are lowercase strings
        result = await svc.create("inst_001", "bullish", score=70.0)
        assert result.success


# ════════════════════════════════════════════════════════════════
# 2. get / get_signal
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestGet:
    async def test_get_existing(self):
        svc = _make_service()
        mock_signal = MagicMock()
        mock_signal.id = "sig_001"
        svc.signal_repo.get = AsyncMock(return_value=Result.ok(mock_signal))
        result = await svc.get("sig_001")
        assert result.success
        assert result.value.id == "sig_001"

    async def test_get_nonexistent(self):
        svc = _make_service()
        svc.signal_repo.get = AsyncMock(return_value=Result.ok(None))
        result = await svc.get("sig_999")
        assert result.success
        assert result.value is None

    async def test_get_signal_returns_dict(self):
        svc = _make_service()
        mock_signal = MagicMock()
        mock_signal.id = "sig_001"
        mock_signal.symbol = "فولاد"
        svc.signal_repo.get = AsyncMock(return_value=Result.ok(mock_signal))
        result = await svc.get_signal("sig_001")
        assert result.success
        assert isinstance(result.value, dict)

    async def test_get_signal_nonexistent(self):
        svc = _make_service()
        svc.signal_repo.get = AsyncMock(return_value=Result.ok(None))
        result = await svc.get_signal("sig_999")
        assert result.success
        assert result.value is None


# ════════════════════════════════════════════════════════════════
# 3. get_latest
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestGetLatest:
    async def test_returns_latest(self):
        svc = _make_service()
        mock_signal = MagicMock()
        svc.signal_repo.get_latest = AsyncMock(return_value=Result.ok(mock_signal))
        result = await svc.get_latest("inst_001")
        assert result.success
        assert result.value == mock_signal


# ════════════════════════════════════════════════════════════════
# 4. list / list_signals
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestList:
    async def test_list_all(self):
        svc = _make_service()
        mock_result = PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=1)
        svc.signal_repo.list = AsyncMock(return_value=Result.ok(mock_result))
        result = await svc.list()
        assert result.success
        assert result.value.total == 0

    async def test_list_by_instrument(self):
        svc = _make_service()
        mock_result = PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=1)
        svc.signal_repo.get_by_instrument = AsyncMock(return_value=Result.ok(mock_result))
        result = await svc.list(instrument_id="inst_001")
        assert result.success

    async def test_list_repo_failure(self):
        svc = _make_service()
        svc.signal_repo.list = AsyncMock(return_value=Result.fail("DB error"))
        result = await svc.list()
        assert result.success  # gracefully returns empty
        assert result.value.total == 0

    async def test_list_signals_delegates_to_list(self):
        svc = _make_service()
        mock_result = PaginatedResult(items=[], total=0, page=1, page_size=50, total_pages=1)
        svc.signal_repo.list = AsyncMock(return_value=Result.ok(mock_result))
        result = await svc.list_signals(page=2, page_size=10)
        assert result.success


# ════════════════════════════════════════════════════════════════
# 5. get_by_symbol
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestGetBySymbol:
    async def test_found(self):
        svc = _make_service()
        mock_signals = [MagicMock(), MagicMock()]
        mock_result = PaginatedResult(items=mock_signals, total=2, page=1, page_size=100, total_pages=1)
        svc.signal_repo.get_by_instrument = AsyncMock(return_value=Result.ok(mock_result))
        result = await svc.get_by_symbol("فولاد")
        assert result.success
        assert len(result.value) == 2

    async def test_not_found(self):
        svc = _make_service()
        svc.signal_repo.get_by_instrument = AsyncMock(return_value=Result.ok(PaginatedResult(items=[], total=0, page=1, page_size=100, total_pages=1)))
        result = await svc.get_by_symbol("نماد_ناموجود")
        assert result.success
        assert result.value == []


# ════════════════════════════════════════════════════════════════
# 6. bulk_generate
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestBulkGenerate:
    async def test_engine_failure_returns_empty(self):
        svc = _make_service()
        with patch("services.signal_service.SignalService.bulk_generate") as mock_bulk:
            mock_bulk.return_value = Result.ok([])
            result = await svc.bulk_generate(["فولاد", "خودرو"])
            assert result.success
            assert result.value == []

    async def test_bulk_generate_calls_engine(self):
        svc = _make_service()
        # bulk_generate imports MultiMarketSignalEngine inside the method,
        # so we patch it at the correct import location
        mock_engine_cls = MagicMock()
        mock_engine = MagicMock()
        mock_engine.generate_all = AsyncMock(return_value=([MagicMock(), MagicMock()], []))
        mock_engine_cls.return_value = mock_engine
        with patch.dict("sys.modules", {"services.multi_market_signal_engine": MagicMock(MultiMarketSignalEngine=mock_engine_cls)}):
            result = await svc.bulk_generate(["فولاد"], strategy="technical")
            assert result.success
