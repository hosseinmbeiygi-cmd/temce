"""Regression tests for audit fixes (temce audit report).

Covers:
  BT-001/BT-002: FIFO lot accounting in PositionManager/PortfolioManager.
  BT-009:        Look-ahead bias — orders execute on the NEXT bar's open.
  BT-013/MKT-001: Tehran timezone-aware session checks.
  MKT-002:       Halted instruments rejected by the rule engine.
  RISK-001/002:  VaR/CVaR reported as positive loss figures.
  ML-001:        Leakage-safe normalization (fit on train only).
  ML-004:        No fictional accuracy promotion after retrain.
  BT-011:        Corporate action as-of adjustment.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import numpy as np
import pytest

# ── BT-001: FIFO position accounting ────────────────────────────────────────


class TestFifoPositionManager:
    def _fill(self, side, qty, price):
        from backtesting.types import FillEvent

        return FillEvent(
            order_id="t", instrument_id="X", side=side, quantity=qty, price=price,
        )

    def test_fifo_realized_pnl(self):
        from backtesting.engine.position_manager import PositionManager

        pm = PositionManager()
        pm.update(self._fill("buy", 100, 10.0))
        pm.update(self._fill("buy", 100, 20.0))
        pm.update(self._fill("sell", 100, 25.0))
        pos = pm.get_position("X")
        # FIFO: the 10.0 lot is sold first → pnl = (25-10)*100
        assert pos.realized_pnl == pytest.approx(1500.0)
        assert pos.quantity == 100

    def test_fifo_matches_trade_metrics(self):
        from backtesting.engine.position_manager import PositionManager

        pm = PositionManager()
        pm.update(self._fill("buy", 50, 10.0))
        pm.update(self._fill("buy", 50, 20.0))
        pm.update(self._fill("sell", 80, 30.0))
        # FIFO: 50 @10 then 30 @20 → (30-10)*50 + (30-20)*30 = 1300
        assert pm.get_total_realized_pnl() == pytest.approx(1300.0)

    def test_avg_price_recomputed_from_lots(self):
        from backtesting.engine.position_manager import PositionManager

        pm = PositionManager()
        pm.update(self._fill("buy", 100, 10.0))
        pm.update(self._fill("buy", 100, 30.0))
        pos = pm.get_position("X")
        assert pos.avg_price == pytest.approx(20.0)


class TestFifoPortfolioManager:
    def _fill(self, side, qty, price, commission=0.0):
        from backtesting.types import FillEvent
        from core.time import utc_now_naive

        return FillEvent(
            order_id=f"t_{utc_now_naive().isoformat()}",
            instrument_id="X", side=side, quantity=qty, price=price,
            commission=commission,
        )

    def test_fifo_sell_pnl_uses_oldest_lot(self):
        from backtesting.engine.portfolio import PortfolioManager

        pm = PortfolioManager()
        pm.reset(1_000_000)
        pm.update_fill_sync(self._fill("buy", 100, 10.0))
        pm.update_fill_sync(self._fill("buy", 100, 20.0))
        pm.update_fill_sync(self._fill("sell", 100, 25.0))
        # PortfolioManager.get_position returns the int quantity; realized PnL
        # is verified via FIFO cash accounting instead.
        assert pm.get_position("X") == 100
        # Cash: 1M - 1000 - 2000 + 2500 = 999,500.
        # Remaining 100 shares @ FIFO avg 20 → positions value 2,000.
        # NAV = 999,500 + 2,000 = 1,001,500 (profit 1,500 = FIFO realized PnL).
        assert pm.get_nav() == pytest.approx(1_001_500.0)

    def test_adjust_positions_rebuilds_lots(self):
        """BT-015: corporate action must rebuild lots, not just totals."""
        from backtesting.engine.portfolio import PortfolioManager

        pm = PortfolioManager()
        pm.reset(1_000_000)
        pm.update_fill_sync(self._fill("buy", 100, 10.0))
        pm.adjust_positions("X", 2.0)  # 2:1 split → 100 × 2 = 200 shares
        assert pm.get_position("X") == 200
        lots = pm.get_open_lots("X")
        assert lots == [(200, 5.0)]
        # Selling all at 6.0 realizes (6-5)*200 = 200 (cash check below)
        pm.update_fill_sync(self._fill("sell", 200, 6.0))
        # Cash: 1M - 1000 + 1200 = 1,000,200 → profit 200 = FIFO realized
        assert pm.get_nav() == pytest.approx(1_000_200.0)


# ── BT-009: look-ahead bias ─────────────────────────────────────────────────


class TestLookAheadBias:
    def test_order_executes_on_next_bar_open(self):
        """Signal on bar t must fill at bar t+1 open, not bar t close."""
        from backtesting.engine.backtest_engine import BacktestEngine

        class OneShotStrategy:
            name = "oneshot"

            def reset(self):
                self.done = False

            def on_bar(self, bar):
                if not self.done:
                    self.done = True
                    return [SimpleOrder()]
                return []

        class SimpleOrder:
            instrument_id = "X"
            side = "buy"
            quantity = 10
            price = 0.0
            order_id = "o1"

        bars = [
            {"timestamp": datetime(2026, 1, 1, tzinfo=UTC), "open": 10.0, "close": 11.0, "prices": {"X": 11.0}},
            {"timestamp": datetime(2026, 1, 2, tzinfo=UTC), "open": 12.0, "close": 13.0, "prices": {"X": 13.0}},
            {"timestamp": datetime(2026, 1, 3, tzinfo=UTC), "open": 14.0, "close": 15.0, "prices": {"X": 15.0}},
        ]

        engine = BacktestEngine(initial_capital=10_000)

        import asyncio as _asyncio

        result = _asyncio.run(engine.run(OneShotStrategy(), bars))
        assert result.trades, "order must fill"
        # Fill price must be bar2's open (12) + slippage, NOT bar1 close (11).
        fill_price = result.trades[0].price
        assert fill_price >= 12.0, f"filled at {fill_price} — look-ahead not fixed"

    def test_last_bar_order_never_fills(self):
        """Orders queued on the final bar cannot execute (market closed)."""
        from backtesting.engine.backtest_engine import BacktestEngine

        class AlwaysBuy:
            name = "always"

            def reset(self):
                pass

            def on_bar(self, bar):
                return [SimpleOrder()]

        class SimpleOrder:
            instrument_id = "X"
            side = "buy"
            quantity = 1
            price = 0.0
            order_id = "o"

        bars = [
            {"timestamp": datetime(2026, 1, i, tzinfo=UTC), "open": 10.0, "close": 10.0}
            for i in range(1, 4)
        ]
        engine = BacktestEngine(initial_capital=10_000)
        result = asyncio.run(engine.run(AlwaysBuy(), bars))
        # 3 bars: fills possible after bar1 and bar2 → at most 2, never 3.
        assert len(result.trades) <= 2


# ── BT-013 / MKT-001: Tehran timezone ──────────────────────────────────────


class TestTehranClock:
    def test_clock_converts_naive_to_tehran(self):
        from backtesting.engine.clock import Clock

        c = Clock(start=datetime(2026, 1, 1, 6, 0))  # naive → UTC → 09:30 Tehran
        assert c.now.hour == 9 and c.now.minute == 30

    def test_market_open_uses_tehran_time(self):
        from backtesting.engine.clock import Clock

        # 03:59 UTC = 07:29 Tehran → closed; 05:30 UTC = 09:00 Tehran → open
        c = Clock(start=datetime(2026, 1, 1, 3, 59, tzinfo=UTC))
        assert c.is_market_open() is False
        c.jump_to(datetime(2026, 1, 1, 5, 30, tzinfo=UTC))
        assert c.is_market_open() is True

    def test_rule_engine_session_is_tehran_aware(self):
        from backtesting.market.rule_engine import MarketRuleEngine

        engine = MarketRuleEngine()
        tehran_noon = datetime(2026, 1, 1, 11, 0, tzinfo=ZoneInfo("Asia/Tehran"))
        assert engine.check_session_status("tse", tehran_noon).value.lower() == "open"

        # Same wall-clock instant expressed in UTC: 11:00 Tehran = 07:30 UTC → OPEN
        utc_equivalent = datetime(2026, 1, 1, 7, 30, tzinfo=UTC)
        assert engine.check_session_status("tse", utc_equivalent).value.lower() == "open"

        # 13:00 UTC = 16:30 Tehran → CLOSED
        assert engine.check_session_status("tse", datetime(2026, 1, 1, 13, 0, tzinfo=UTC)).value.lower() == "closed"


# ── MKT-002: halted instruments ─────────────────────────────────────────────


class TestHaltedInstruments:
    def test_halted_order_rejected(self):
        from backtesting.market.rule_engine import MarketRuleEngine
        from backtesting.types import OrderEvent

        engine = MarketRuleEngine()
        order = OrderEvent(instrument_id="X", side="buy", quantity=100, price=1000.0)
        ok, _ = engine.validate_order("tse", order)
        assert ok

        engine.set_halted("tse", "X")
        ok, reason = engine.validate_order("tse", order)
        assert not ok and "halted" in reason

        engine.set_halted("tse", "X", halted=False)
        ok, _ = engine.validate_order("tse", order)
        assert ok


# ── RISK-001/002: VaR/CVaR positive loss ───────────────────────────────────


class TestVarCvarConventions:
    def test_var_is_positive_loss(self):
        from backtesting.risk.var import ValueAtRisk

        returns = list(np.random.default_rng(42).normal(-0.001, 0.02, 500))
        var = ValueAtRisk(confidence=0.95).compute(returns)
        assert var > 0, "VaR must be a positive loss figure"

    def test_parametric_var_is_positive(self):
        from backtesting.risk.var import ValueAtRisk

        var = ValueAtRisk(confidence=0.95).compute_parametric([0.01, -0.02, 0.005, -0.01, 0.0, -0.03, 0.02])
        assert var > 0

    def test_cvar_is_positive_and_geq_var(self):
        from backtesting.risk.cvar import ConditionalValueAtRisk
        from backtesting.risk.var import ValueAtRisk

        rng = np.random.default_rng(7)
        returns = list(rng.normal(0.0, 0.02, 1000))
        var = ValueAtRisk(confidence=0.95).compute(returns)
        cvar = ConditionalValueAtRisk(confidence=0.95).compute(returns)
        assert cvar > 0
        assert cvar >= var * 0.99  # expected shortfall ≥ VaR (within numeric slack)


# ── ML-001: leakage-safe normalization ─────────────────────────────────────


class TestLeakageSafeNormalization:
    def test_stats_fitted_on_train_only(self):
        from ml.dataset_builder import DatasetBuilder

        data = [1.0] * 80 + [1000.0] * 20  # test slice carries an outlier
        train, test, stats = DatasetBuilder().fit_normalize(data, test_size=0.2)
        # Train mean must NOT include the test outlier
        assert stats["mean"] == pytest.approx(1.0)
        # Constant train slice → zero std → zeros; the point is the STATS are
        # train-only (mean == 1.0 proves the 1000s were excluded).
        assert all(v == 0.0 for v in test)

    def test_apply_normalization_uses_saved_stats(self):
        from ml.dataset_builder import DatasetBuilder

        builder = DatasetBuilder()
        _, _, stats = builder.fit_normalize([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0])
        out = builder.apply_normalization([5.0], stats)
        assert out[0] == pytest.approx((5.0 - stats["mean"]) / stats["std"])


# ── ML-004: no fictional accuracy promotion ────────────────────────────────


class TestNoFictionalAccuracy:
    def test_no_plus_3_percent_promotion_in_source(self):
        import inspect

        import services.auto_retrain_pipeline as mod

        src = inspect.getsource(mod)
        # The literal promotion expression must be gone (docstring mentions are
        # fine — this checks the executable pattern).
        assert "min(current_accuracy + 0.03" not in src
        assert "min(report.old_accuracy + 0.02, 0.62)" not in src

    async def test_holdout_returns_none_without_db(self, monkeypatch):
        import core.database as _db

        # Control the data source explicitly: another test module in the same
        # session may already have initialised a real factory, in which case
        # the "unavailable" branch would query the live DB instead.
        monkeypatch.setattr(_db, "async_session_factory", None, raising=False)
        from services.auto_retrain_pipeline import AutoRetrainPipeline

        pipeline = AutoRetrainPipeline()
        result = await pipeline._evaluate_holdout_accuracy("stock")
        assert result is None  # no DB → must NOT return a number


# ── BT-011: corporate action as-of ─────────────────────────────────────────


class TestCorporateActionAsOf:
    def test_action_only_adjusts_before_effective_date(self):
        from backtesting.corporate_actions import CorporateActionAdjuster
        from domain.market_data.corporate_action import CorporateAction

        adjuster = CorporateActionAdjuster()
        points = [
            (datetime(2026, 1, 1, tzinfo=UTC), 100.0),
            (datetime(2026, 1, 2, tzinfo=UTC), 100.0),
            (datetime(2026, 1, 3, tzinfo=UTC), 50.0),   # post-split price
            (datetime(2026, 1, 4, tzinfo=UTC), 51.0),
        ]
        actions = [
            CorporateAction(
                id="ca1", instrument_id="X", action_type="stock_split",
                ratio=2.0, date=datetime(2026, 1, 3).date(),
            )
        ]
        adjusted = adjuster.adjust_prices_with_dates(points, actions)
        # Pre-split points doubled (÷ factor 0.5... actually factor=1/ratio=0.5 → /0.5 = ×2)
        assert adjusted[0] == pytest.approx(200.0)
        assert adjusted[1] == pytest.approx(200.0)
        # Post-split points untouched
        assert adjusted[2] == pytest.approx(50.0)
        assert adjusted[3] == pytest.approx(51.0)

    def test_future_action_ignored_with_as_of(self):
        from backtesting.corporate_actions import CorporateActionAdjuster
        from domain.market_data.corporate_action import CorporateAction

        adjuster = CorporateActionAdjuster()
        points = [(datetime(2026, 1, 1, tzinfo=UTC), 100.0)]
        actions = [
            CorporateAction(
                id="ca1", instrument_id="X", action_type="stock_split",
                ratio=2.0, date=datetime(2026, 6, 1).date(),
            )
        ]
        # as_of before the action → no adjustment (no look-ahead)
        adjusted = adjuster.adjust_prices_with_dates(points, actions, as_of=datetime(2026, 2, 1, tzinfo=UTC))
        assert adjusted[0] == pytest.approx(100.0)


# ── SRV-001: durable queue API surface ─────────────────────────────────────


class TestDurableOutcomeQueue:
    def test_stats_include_redis_recovery(self):
        from services.accuracy_outcome_queue import AccuracyOutcomeQueue

        stats = AccuracyOutcomeQueue().stats()
        assert "redis_recovered_total" in stats

    async def test_recover_from_redis_no_redis(self, monkeypatch):
        from services.accuracy_outcome_queue import AccuracyOutcomeQueue

        class _FakeCache:
            is_connected = False
            client = None

        monkeypatch.setattr("core.cache.get_cache", lambda: _FakeCache())
        queue = AccuracyOutcomeQueue()
        assert await queue.recover_from_redis() == 0
