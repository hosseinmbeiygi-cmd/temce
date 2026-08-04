"""
Unit tests for BrsApiJobRegistry — _get_pro_symbols & history job handlers.

Tests:
- ``_get_pro_symbols()`` — queries distinct symbols from the DB
- ``run_job()`` for ``brsapi_gold_currency_pro_history_24h``
- ``run_job()`` for ``brsapi_gold_currency_pro_daily_history``
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ──────────────────────────────────────────────
#  _get_pro_symbols
# ──────────────────────────────────────────────


class TestGetProSymbols:
    """Tests for BrsApiJobRegistry._get_pro_symbols()."""

    @pytest.fixture
    def registry(self):
        from brsapi.jobs.registry import BrsApiJobRegistry

        return BrsApiJobRegistry()

    def _mock_session_execute(self, symbols: list[str]) -> AsyncMock:
        """Return an async mock session whose execute() yields rows with given symbols."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.__iter__.return_value = [(s,) for s in symbols]
        mock_session.execute = AsyncMock(return_value=mock_result)
        return mock_session

    def _extract_stmt(self, mock_session) -> str:
        """Return the SQL string that was passed to session.execute()."""
        return str(mock_session.execute.call_args[0][0]).lower()

    async def test_returns_symbols(self, registry):
        """Should return distinct symbols when rows exist."""
        mock_session = ["XAUUSD", "IR_GOLD_18K", "BTC"]
        result = await registry._get_pro_symbols(mock_session, max_symbols=50)
        assert result == ["XAUUSD", "IR_GOLD_18K", "BTC"]

    async def test_respects_max_symbols(self, registry):
        """Should apply LIMIT clause with max_symbols value."""
        mock_session = self._mock_session_execute([f"SYM_{i}" for i in range(100)])
        await registry._get_pro_symbols(mock_session, max_symbols=5)
        stmt = self._extract_stmt(mock_session)
        assert "limit" in stmt
        assert ":param_1" in stmt  # parameterized limit value

    async def test_returns_empty_when_no_rows(self, registry):
        """Should return empty list when no rows in table."""
        mock_session = self._mock_session_execute([])
        result = await registry._get_pro_symbols(mock_session)
        assert result == []

    async def test_filters_none_rows(self, registry):
        """Should filter out None values from result rows."""
        mock_session = ["XAUUSD", None, "BTC", None]
        result = await registry._get_pro_symbols(mock_session)
        assert result == ["XAUUSD", "BTC"]

    async def test_calls_distinct_query(self, registry):
        """Should build a SELECT DISTINCT symbol query against GoldCurrencyProPriceModel."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.__iter__.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await registry._get_pro_symbols(mock_session, max_symbols=10)

        assert mock_session.execute.call_count == 1
        stmt = self._extract_stmt(mock_session)
        assert "distinct" in stmt
        assert "symbol" in stmt
        assert "gold_currency_pro_prices" in stmt
        assert "limit" in stmt

    async def test_default_max_symbols_is_50(self, registry):
        """Should default to LIMIT 50 when max_symbols not specified."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.__iter__.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await registry._get_pro_symbols(mock_session)

        stmt = self._extract_stmt(mock_session)
        assert "limit" in stmt
        assert ":param_1" in stmt


# ──────────────────────────────────────────────
#  History job handlers
# ──────────────────────────────────────────────


class TestHistoryJobHandlers:
    """Tests for Gold_Currency_Pro history jobs (24h + daily) in run_job()."""

    MOCK_SYMBOLS = ["XAUUSD", "BTC", "EURUSD"]

    @pytest.fixture
    def registry(self):
        from brsapi.jobs.registry import BRsAPI_SYNC_JOBS, BrsApiJobRegistry

        reg = BrsApiJobRegistry()
        reg.register_many(BRsAPI_SYNC_JOBS)
        return reg

    @pytest.fixture
    def mock_service(self):
        """Return an AsyncMock BrsApiSyncService with history methods mocked."""
        svc = AsyncMock()
        svc.sync_gold_currency_pro_history_24h = AsyncMock(
            return_value=MagicMock(
                success=True,
                items_count=150,
                endpoint="Gold_Currency_Pro/24h",
                duration_ms=1200.0,
            )
        )
        svc.sync_gold_currency_pro_daily_history = AsyncMock(
            return_value=MagicMock(
                success=True,
                items_count=365,
                endpoint="Gold_Currency_Pro/Daily",
                duration_ms=800.0,
            )
        )
        return svc

    @pytest.fixture
    def mock_session(self):
        """Return an AsyncMock session with commit mocked."""
        session = AsyncMock()
        session.commit = AsyncMock()
        return session

    async def _run(
        self,
        registry,
        mock_session,
        mock_service,
        job_name: str,
        symbols=None,
    ):
        """Execute ``run_job`` under all required patches."""
        if symbols is None:
            symbols = self.MOCK_SYMBOLS
        registry._get_pro_symbols = AsyncMock(return_value=symbols)

        with (
            patch("brsapi.jobs.registry.get_session") as mock_gs,
            patch(
                "brsapi.jobs.registry.get_client",
                return_value=AsyncMock(return_value=MagicMock()),
            ),
            patch("brsapi.jobs.registry.BrsApiSyncService") as mock_svc_cls,
        ):
            mock_gs.return_value.__aiter__.return_value = [mock_session]
            mock_svc_cls.return_value = mock_service
            return await registry.run_job(job_name)

    # ── 24h history ───────────────────────────

    async def test_history_24h_calls_get_pro_symbols(self, registry, mock_session, mock_service):
        """Should call _get_pro_symbols with max_symbols=20."""
        await self._run(registry, mock_session, mock_service, "brsapi_gold_currency_pro_history_24h")
        registry._get_pro_symbols.assert_awaited_once_with(mock_session, max_symbols=20)

    async def test_history_24h_calls_sync_for_each_symbol(self, registry, mock_session, mock_service):
        """Should call sync_gold_currency_pro_history_24h for each symbol."""
        await self._run(registry, mock_session, mock_service, "brsapi_gold_currency_pro_history_24h")
        assert mock_service.sync_gold_currency_pro_history_24h.call_count == len(self.MOCK_SYMBOLS)
        for sym in self.MOCK_SYMBOLS:
            mock_service.sync_gold_currency_pro_history_24h.assert_any_await(mock_session, symbol=sym)

    async def test_history_24h_commits_at_end(self, registry, mock_session, mock_service):
        """Should commit session after all symbols are processed."""
        await self._run(registry, mock_session, mock_service, "brsapi_gold_currency_pro_history_24h")
        mock_session.commit.assert_awaited_once()

    async def test_history_24h_returns_none_when_no_symbols(self, registry, mock_session, mock_service):
        """Should return None and log warning when no Pro symbols found."""
        result = await self._run(
            registry,
            mock_session,
            mock_service,
            "brsapi_gold_currency_pro_history_24h",
            symbols=[],
        )
        assert result is None
        mock_service.sync_gold_currency_pro_history_24h.assert_not_called()

    # ── Daily history ─────────────────────────

    async def test_daily_history_calls_get_pro_symbols(self, registry, mock_session, mock_service):
        """Should call _get_pro_symbols with max_symbols=20."""
        await self._run(
            registry,
            mock_session,
            mock_service,
            "brsapi_gold_currency_pro_daily_history",
        )
        registry._get_pro_symbols.assert_awaited_once_with(mock_session, max_symbols=20)

    async def test_daily_history_calls_sync_for_each_symbol(self, registry, mock_session, mock_service):
        """Should call sync_gold_currency_pro_daily_history for each symbol."""
        await self._run(
            registry,
            mock_session,
            mock_service,
            "brsapi_gold_currency_pro_daily_history",
        )
        assert mock_service.sync_gold_currency_pro_daily_history.call_count == len(self.MOCK_SYMBOLS)
        for sym in self.MOCK_SYMBOLS:
            mock_service.sync_gold_currency_pro_daily_history.assert_any_await(mock_session, symbol=sym)

    async def test_daily_history_commits_at_end(self, registry, mock_session, mock_service):
        """Should commit session after all symbols are processed."""
        await self._run(
            registry,
            mock_session,
            mock_service,
            "brsapi_gold_currency_pro_daily_history",
        )
        mock_session.commit.assert_awaited_once()

    async def test_daily_history_returns_none_when_no_symbols(self, registry, mock_session, mock_service):
        """Should return None and log warning when no Pro symbols found."""
        result = await self._run(
            registry,
            mock_session,
            mock_service,
            "brsapi_gold_currency_pro_daily_history",
            symbols=[],
        )
        assert result is None
        mock_service.sync_gold_currency_pro_daily_history.assert_not_called()


# ──────────────────────────────────────────────
#  Gold_Currency composite job handler
# ──────────────────────────────────────────────


class TestGoldCurrencyHandler:
    """Tests for the gold_currency composite job in run_job()."""

    @pytest.fixture
    def registry(self):
        from brsapi.jobs.registry import BRsAPI_SYNC_JOBS, BrsApiJobRegistry

        reg = BrsApiJobRegistry()
        reg.register_many(BRsAPI_SYNC_JOBS)
        return reg

    @pytest.fixture
    def mock_session(self):
        """Return an AsyncMock session."""
        session = AsyncMock()
        session.commit = AsyncMock()
        return session

    def _make_report(self, endpoint: str, success: bool = True, items: int = 50, ms: float = 500.0):
        """Create a mock SyncReport."""
        return MagicMock(
            endpoint=endpoint,
            success=success,
            items_count=items,
            duration_ms=ms,
        )

    async def _run(
        self,
        registry,
        mock_session,
        mock_reports: list,
        job_name: str = "brsapi_gold_currency",
    ) -> tuple:
        """Execute run_job under all required patches.

        Returns (result, mock_svc) for call verification.
        """
        with (
            patch("brsapi.jobs.registry.get_session") as mock_gs,
            patch(
                "brsapi.jobs.registry.get_client",
                return_value=AsyncMock(return_value=MagicMock()),
            ),
            patch("brsapi.jobs.registry.BrsApiSyncService") as mock_svc_cls,
        ):
            mock_gs.return_value.__aiter__.return_value = [mock_session]
            mock_svc = AsyncMock()
            mock_svc.sync_gold_currency = AsyncMock(return_value=mock_reports)
            mock_svc_cls.return_value = mock_svc
            result = await registry.run_job(job_name)
            return result, mock_svc

    async def test_calls_sync_gold_currency(self, registry, mock_session):
        """Should call service.sync_gold_currency(session)."""
        reports = [self._make_report("Gold_Currency/gold")]
        _, mock_svc = await self._run(registry, mock_session, reports)
        mock_svc.sync_gold_currency.assert_awaited_once_with(mock_session)

    async def test_returns_first_report(self, registry, mock_session):
        """Should return the first SyncReport when multiple sections synced."""
        reports = [
            self._make_report("Gold_Currency/gold", items=12),
            self._make_report("Gold_Currency/currency", items=30),
            self._make_report("Gold_Currency/cryptocurrency", items=18),
        ]
        result, _ = await self._run(registry, mock_session, reports)
        assert result is not None
        assert result.items_count == 12
        assert result.endpoint == "Gold_Currency/gold"

    async def test_returns_none_when_reports_empty(self, registry, mock_session):
        """Should return None when sync_gold_currency returns empty list."""
        result, _ = await self._run(registry, mock_session, [])
        assert result is None

    async def test_passes_failure_status(self, registry, mock_session):
        """Should pass through failure status from the sync report."""
        reports = [self._make_report("Gold_Currency/gold", success=False, items=0)]
        result, _ = await self._run(registry, mock_session, reports)
        assert result is not None
        assert not result.success
        assert result.items_count == 0

    async def test_does_not_call_get_pro_symbols(self, registry, mock_session):
        """Should NOT call _get_pro_symbols (unlike history handlers)."""
        registry._get_pro_symbols = AsyncMock(return_value=["XAUUSD"])
        reports = [self._make_report("Gold_Currency/gold")]
        result, mock_svc = await self._run(registry, mock_session, reports)
        registry._get_pro_symbols.assert_not_called()  # ── Unknown job ───────────────────────────

    async def test_unknown_job_returns_none(self, registry):
        """Should return None for unknown job names."""
        result = await registry.run_job("nonexistent_job")
        assert result is None


# ── Gold_Currency_Pro composite job handler ─────────────────────


class TestGoldCurrencyProHandler:
    """Tests for the gold_currency_pro composite job in run_job()."""

    @pytest.fixture
    def registry(self):
        from brsapi.jobs.registry import BRsAPI_SYNC_JOBS, BrsApiJobRegistry

        reg = BrsApiJobRegistry()
        reg.register_many(BRsAPI_SYNC_JOBS)
        return reg

    @pytest.fixture
    def mock_session(self):
        """Return an AsyncMock session."""
        session = AsyncMock()
        session.commit = AsyncMock()
        return session

    def _make_report(self, endpoint: str, success: bool = True, items: int = 50, ms: float = 500.0):
        """Create a mock SyncReport."""
        return MagicMock(
            endpoint=endpoint,
            success=success,
            items_count=items,
            duration_ms=ms,
        )

    async def _run(
        self,
        registry,
        mock_session,
        mock_reports: list,
        job_name: str = "brsapi_gold_currency_pro",
    ) -> tuple:
        """Execute run_job under all required patches.

        Returns (result, mock_svc) for call verification.
        """
        with (
            patch("brsapi.jobs.registry.get_session") as mock_gs,
            patch(
                "brsapi.jobs.registry.get_client",
                return_value=AsyncMock(return_value=MagicMock()),
            ),
            patch("brsapi.jobs.registry.BrsApiSyncService") as mock_svc_cls,
        ):
            mock_gs.return_value.__aiter__.return_value = [mock_session]
            mock_svc = AsyncMock()
            mock_svc.sync_gold_currency_pro = AsyncMock(return_value=mock_reports)
            mock_svc_cls.return_value = mock_svc
            result = await registry.run_job(job_name)
            return result, mock_svc

    async def test_calls_sync_gold_currency_pro(self, registry, mock_session):
        """Should call service.sync_gold_currency_pro(session)."""
        reports = [self._make_report("Gold_Currency_Pro/pro_prices")]
        _, mock_svc = await self._run(registry, mock_session, reports)
        mock_svc.sync_gold_currency_pro.assert_awaited_once_with(mock_session)

    async def test_returns_first_report(self, registry, mock_session):
        """Should return the first SyncReport when multiple sections synced."""
        reports = [
            self._make_report("Gold_Currency_Pro/pro_prices", items=25),
            self._make_report("Gold_Currency_Pro/sections", items=10),
        ]
        result, _ = await self._run(registry, mock_session, reports)
        assert result is not None
        assert result.items_count == 25
        assert result.endpoint == "Gold_Currency_Pro/pro_prices"

    async def test_returns_none_when_reports_empty(self, registry, mock_session):
        """Should return None when sync_gold_currency_pro returns empty list."""
        result, _ = await self._run(registry, mock_session, [])
        assert result is None

    async def test_passes_failure_status(self, registry, mock_session):
        """Should pass through failure status from the sync report."""
        reports = [self._make_report("Gold_Currency_Pro/pro_prices", success=False, items=0)]
        result, _ = await self._run(registry, mock_session, reports)
        assert result is not None
        assert not result.success
        assert result.items_count == 0

    async def test_does_not_call_get_pro_symbols(self, registry, mock_session):
        """Should NOT call _get_pro_symbols (unlike history handlers)."""
        registry._get_pro_symbols = AsyncMock(return_value=["XAUUSD"])
        reports = [self._make_report("Gold_Currency_Pro/pro_prices")]
        _, mock_svc = await self._run(registry, mock_session, reports)
        registry._get_pro_symbols.assert_not_called()

    async def test_unknown_job_returns_none(self, registry):
        """Should return None for unknown job names."""
        result = await registry.run_job("nonexistent_job")
        assert result is None
