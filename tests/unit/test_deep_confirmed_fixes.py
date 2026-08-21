"""Regression tests for confirmed issues from the deep runtime audit."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest

from backtesting.observability.simulation_logger import SimulationLogger
from backtesting.portfolio.ledger import PortfolioLedger
from brsapi.client import _redact_sensitive_text
from brsapi.models.tsetmc import SymbolSnapshotModel
from brsapi.repositories.base import BulkUpsertRepository, _redact_params


class TestPortfolioLedgerAccounting:
    def test_buy_and_sell_realized_pnl_is_net_of_all_fees(self) -> None:
        ledger = PortfolioLedger(
            initial_capital=1_000_000.0,
            commission_pct=0.01,
            tax_pct=0.02,
            settlement_days=0,
        )

        assert ledger.buy("TEST", 100, 100.0, date(2026, 8, 16)) is not None
        assert ledger.sell("TEST", 100, 110.0, date(2026, 8, 16)) is not None

        # Buy cost basis = 101/share; sell costs = 110 commission + 220 tax.
        # Net realized PnL = (110 - 101) * 100 - 110 - 220 = 570.
        assert ledger.get_realized_pnl() == pytest.approx(570.0)
        assert ledger.get_summary()["nav"] == pytest.approx(1_000_570.0)

    def test_retained_earnings_increase_preserves_total_cost(self) -> None:
        ledger = PortfolioLedger(
            initial_capital=100_000.0,
            commission_pct=0.0,
            tax_pct=0.0,
            settlement_days=0,
        )
        trade_date = date(2026, 8, 16)
        assert ledger.buy("TEST", 100, 100.0, trade_date) is not None
        nav_before = ledger.get_nav({"TEST": 100.0})

        ledger.apply_capital_increase_retained("TEST", 2.0, trade_date)

        assert ledger.get_positions()["TEST"] == 200
        assert ledger.get_nav({"TEST": 50.0}) == pytest.approx(nav_before)
        assert ledger.get_realized_pnl() == pytest.approx(0.0)

    def test_settlement_skips_thursday_and_friday(self) -> None:
        ledger = PortfolioLedger(initial_capital=100_000.0, settlement_days=1)
        # Wednesday 2026-08-19 -> next Tehran trading day is Saturday 2026-08-22.
        assert ledger._add_settlement_days(date(2026, 8, 19)) == date(2026, 8, 22)


class TestSafeBulkUpsert:
    @pytest.mark.asyncio
    async def test_rejects_unknown_or_injected_column_names(self) -> None:
        session = AsyncMock()
        repo = BulkUpsertRepository(session, SymbolSnapshotModel)

        with pytest.raises(ValueError, match="(Invalid SQL identifier|Unknown column)"):
            await repo.bulk_insert([{"symbol; DROP TABLE users; --": "x"}])

        session.execute.assert_not_awaited()


class TestCredentialRedaction:
    def test_redacts_query_credentials_and_audit_params(self) -> None:
        assert _redact_sensitive_text(
            "GET https://api.test/path?key=secret-value&l18=فولاد"
        ) == "GET https://api.test/path?key=[REDACTED]&l18=فولاد"
        assert _redact_params({"key": "secret", "l18": "فولاد"}) == {
            "key": "[REDACTED]",
            "l18": "فولاد",
        }


class TestSimulationLoggerBounds:
    def test_default_history_is_bounded(self) -> None:
        logger = SimulationLogger("bounded-test")
        for i in range(10_001):
            logger.info("TEST", str(i))

        assert len(logger.entries) == 10_000
        assert logger.entries[0].message == "1"
        assert logger.entries[-1].message == "10000"
