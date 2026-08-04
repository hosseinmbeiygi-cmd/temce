"""
تست end-to-end زنجیره داده→سیگنال
بررسی می‌کند که داده از دیتابیس خوانده شده و سیگنال تولید می‌شود.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _SessionCtx:
    """Async context manager that yields the exact mock session.

    ``AsyncMock``'s default ``__aenter__`` yields a *different* child mock, so
    the engine would run against a fresh mock whose ``execute().fetchall()``
    returns coroutines instead of rows. This thin context manager mimics a real
    SQLAlchemy ``AsyncSession`` (which yields itself on ``async with``).
    """

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        return False


class TestSignalPipelineE2E:
    """تست زنجیره کامل داده→سیگنال"""

    @pytest.mark.asyncio
    async def test_gold_signal_with_data(self):
        """سیگنال طلا باید با داده gold_coin_prices تولید شود."""
        from services.multi_market_signal_engine import MultiMarketSignalEngine

        engine = MultiMarketSignalEngine()

        mock_session = AsyncMock()

        # Mock gold coin prices
        mock_result1 = MagicMock()
        mock_result1.fetchall.return_value = [
            ("gold_18k", "سکه طلای ۱۸ عیار", 250000000, 5000000, 2.0),
            ("gold_24h", "طلای ۲۴ ساعته", 300000000, -3000000, -1.0),
        ]

        # Mock gold 24h (empty - should fallback)
        mock_result2 = MagicMock()
        mock_result2.fetchall.return_value = []

        # Mock gold history (empty)
        mock_result3 = MagicMock()
        mock_result3.fetchall.return_value = []

        call_count = 0

        async def mock_execute(query, params=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_result1  # gold_coin_prices
            elif call_count == 2:
                return mock_result2  # gold_24h
            else:
                return mock_result3  # gold_coin_history / XAUUSD

        mock_session.execute = mock_execute

        with patch("core.database.async_session_factory") as mock_factory:
            mock_factory.return_value = _SessionCtx(mock_session)

            signals = await engine._signals_gold()

            assert len(signals) > 0, "باید حداقل یک سیگنال طلا تولید شود"
            assert any(s.market == "gold" for s in signals)

    @pytest.mark.asyncio
    async def test_currency_signal_with_data(self):
        """سیگنال ارز باید با داده currency_prices تولید شود."""
        from services.multi_market_signal_engine import MultiMarketSignalEngine

        engine = MultiMarketSignalEngine()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("USD", "دلار آمریکا", 500000, 5000, 1.0),
            ("EUR", "یورو", 550000, -2000, -0.4),
        ]

        async def mock_execute(query, params=None):
            return mock_result

        mock_session.execute = mock_execute

        with patch("core.database.async_session_factory") as mock_factory:
            mock_factory.return_value = _SessionCtx(mock_session)

            signals = await engine._signals_currency()

            assert len(signals) > 0, "باید حداقل یک سیگنال ارز تولید شود"
            assert any(s.market == "currency" for s in signals)

    @pytest.mark.asyncio
    async def test_crypto_signal_without_history(self):
        """سیگنال رمزارز بدون تاریخچه باید fallback تولید کند."""
        from services.multi_market_signal_engine import MultiMarketSignalEngine

        engine = MultiMarketSignalEngine()

        mock_session = AsyncMock()

        # Mock crypto prices
        mock_result1 = MagicMock()
        mock_result1.fetchall.return_value = [
            ("BTC", "Bitcoin", 60000, 2500000000, 3.0, 1e12, 30e9, 1),
        ]

        # Mock empty history
        mock_result2 = MagicMock()
        mock_result2.fetchall.return_value = []

        call_count = 0

        async def mock_execute(query, params=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_result1
            return mock_result2

        mock_session.execute = mock_execute

        with patch("core.database.async_session_factory") as mock_factory:
            mock_factory.return_value = _SessionCtx(mock_session)

            signals = await engine._signals_crypto()

            assert len(signals) > 0, "سیگنال رمزارز حتی بدون تاریخچه باید fallback تولید کند"

    @pytest.mark.asyncio
    async def test_generate_all_returns_tuple(self):
        """generate_all باید tuple (signals, reports) برگرداند."""
        from services.multi_market_signal_engine import MultiMarketSignalEngine

        engine = MultiMarketSignalEngine()

        with patch("core.database.async_session_factory", None):
            result = await engine.generate_all(market_filter="stock")
            assert isinstance(result, tuple), "generate_all باید tuple برگرداند"
            assert len(result) == 2, "tuple باید ۲ عصر داشته باشد"
            signals, reports = result
            assert isinstance(signals, list)
            assert isinstance(reports, list)

    @pytest.mark.asyncio
    async def test_signal_report_structure(self):
        """SignalGenerationReport باید ساختار درستی داشته باشد."""
        from services.multi_market_signal_engine import SignalGenerationReport

        report = SignalGenerationReport(market="stock", success=True, signal_count=5, duration_ms=123.4)
        assert report.market == "stock"
        assert report.success is True
        assert report.signal_count == 5
        assert report.error is None

        fail_report = SignalGenerationReport(
            market="gold",
            success=False,
            error="DB connection failed",
            error_type="ConnectionError",
            duration_ms=50.0,
        )
        assert fail_report.success is False
        assert fail_report.error == "DB connection failed"
        assert fail_report.error_type == "ConnectionError"
