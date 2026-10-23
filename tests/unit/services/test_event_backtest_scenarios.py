"""STEP 7C-1 — deterministic market-microstructure scenarios on existing engines.

Every scenario drives an *existing* extension point only
(``services/event_backtest.py`` and ``services/gold/margin_model.py``); no engine
was modified to make a scenario reachable.  Expectations are hand-computed in the
comments, so a change in the engines' arithmetic breaks these tests loudly rather
than silently shifting numbers.

Scenarios
---------
1. Regulator price-band change      — ``TSERulesEngine(limit_pct)``
2. Trade cancellation               — ``ExecutionEngine.submit`` / ``cancel_all``
3. Symbol halt / resume             — ``TSERulesEngine.can_trade`` + ``MarketState.is_halted``
4. Physical delivery cost           — ``ExecutionEngine(commission_buy, commission_sell)``
5. Margin stop-out                  — ``services.gold.margin_model.simulate_margin_path``
"""

from __future__ import annotations

import pytest

from services.event_backtest import (
    EventBacktestEngine,
    EventType,
    ExecutionEngine,
    MarketEvent,
    MarketState,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    PortfolioEngine,
    SlippageModel,
    TSERulesEngine,
)
from services.gold.margin_model import REQUIRED_MARGIN_KEYS, simulate_margin_path

# ── Shared fixture pieces ─────────────────────────────────────────────────

SYMBOL = "GLD"
CASH = 1_000_000.0

#: Margin configuration used by the stop-out scenarios (no exchange rates are
#: hard-coded in the model, so the test supplies them explicitly).
MARGIN_CONFIG = {
    "initial_margin_ratio": 0.2,
    "maintenance_margin_ratio": 0.1,
    "margin_call_equity_ratio": 1.0,
    "stop_out_equity_ratio": 0.5,
    "contract_size": 100,
}


def _state(**overrides) -> MarketState:
    base = {
        "symbol": SYMBOL,
        "timestamp": 1.0,
        "open": 1_000.0,
        "high": 1_010.0,
        "low": 990.0,
        "close": 1_000.0,
        "volume": 100_000.0,
        "value": 100_000_000.0,
        "bid_price": 999.0,
        "ask_price": 1_000.0,
        "bid_size": 10_000.0,
        "ask_size": 10_000.0,
        "limit_up": 1_050.0,
        "limit_down": 950.0,
        "yesterday_close": 1_000.0,
    }
    base.update(overrides)
    return MarketState(**base)


def _engine(**overrides) -> ExecutionEngine:
    """Execution engine with zero slippage so every fill price is exact."""
    defaults = {
        "commission_buy": 0.001,
        "commission_sell": 0.001,
        "slippage_model": SlippageModel(model_type="fixed", fixed_bps=0.0),
        "participation_rate": 1.0,
    }
    defaults.update(overrides)
    return ExecutionEngine(**defaults)


def _buy(qty: float, price: float = 1_000.0, order_id: str = "B1") -> Order:
    return Order(
        order_id=order_id,
        symbol=SYMBOL,
        side=OrderSide.BUY,
        qty=qty,
        order_type=OrderType.LIMIT,
        limit_price=price,
        timestamp=1.0,
    )


def _sell(qty: float, price: float, order_id: str = "S1") -> Order:
    return Order(
        order_id=order_id,
        symbol=SYMBOL,
        side=OrderSide.SELL,
        qty=qty,
        order_type=OrderType.LIMIT,
        limit_price=price,
        timestamp=2.0,
    )


def _tick() -> MarketEvent:
    return MarketEvent(timestamp=1.0, event_type=EventType.BAR_CLOSE, symbol=SYMBOL)


# ── 1. Regulator price-band change ────────────────────────────────────────


class TestPriceBandChange:
    """The band is a constructor parameter, so a regulator change is one number."""

    @pytest.mark.parametrize(
        ("limit_pct", "yesterday_close", "expected_down", "expected_up"),
        [
            # 1000 * (1 -/+ 0.05)
            (0.05, 1_000.0, 950.0, 1_050.0),
            # regulator tightens the band to 2%
            (0.02, 1_000.0, 980.0, 1_020.0),
            # regulator widens the band to 7%
            (0.07, 1_000.0, 930.0, 1_070.0),
            # fully frozen market: both limits collapse on the close
            (0.0, 1_000.0, 1_000.0, 1_000.0),
            # a different reference price scales proportionally
            (0.05, 4_000.0, 3_800.0, 4_200.0),
        ],
    )
    def test_limits_are_recomputed_from_yesterday_close(
        self, limit_pct, yesterday_close, expected_down, expected_up
    ) -> None:
        down, up = TSERulesEngine(limit_pct=limit_pct).compute_price_limits(yesterday_close)

        assert down == pytest.approx(expected_down, abs=1e-9)
        assert up == pytest.approx(expected_up, abs=1e-9)

    @pytest.mark.parametrize(
        ("limit_pct", "expected_price"),
        [(0.05, 1_040.0), (0.02, 1_020.0), (0.07, 1_040.0)],
    )
    def test_order_price_is_clamped_to_the_active_band(self, limit_pct, expected_price) -> None:
        rules = TSERulesEngine(limit_pct=limit_pct)
        down, up = rules.compute_price_limits(1_000.0)
        state = _state(limit_up=up, limit_down=down)

        # An order 4% above the close is legal under a 5%/7% band (passes through
        # unchanged) but is clamped to +2% under the tightened band.
        assert rules.adjust_price_to_limits(1_040.0, state) == pytest.approx(
            expected_price, abs=1e-9
        )

    @pytest.mark.parametrize(
        ("limit_pct", "fill_price", "fee", "final_cash"),
        [
            # locked at the upper limit: exec_qty = min(100, volume*1.0) = 100,
            # price = limit_up, fee = 100 * price * 0.001,
            # cash = 1_000_000 - (100 * price + fee)
            (0.05, 1_050.0, 105.0, 894_895.0),
            (0.02, 1_020.0, 102.0, 897_898.0),
            (0.07, 1_070.0, 107.0, 892_893.0),
        ],
    )
    def test_narrower_band_lowers_the_price_paid_at_the_limit(
        self, limit_pct, fill_price, fee, final_cash
    ) -> None:
        rules = TSERulesEngine(limit_pct=limit_pct)
        _, up = rules.compute_price_limits(1_000.0)
        # close == limit_up with an empty offer side = a buy locked at the band.
        state = _state(close=up, limit_up=up, ask_size=0.0, ask_queue=100.0, bid_queue=0.0)
        assert rules.is_locked_buy(state) is True

        engine = _engine()
        portfolio = PortfolioEngine(initial_cash=CASH)
        engine.submit(_buy(100.0))
        fills = engine.match(_tick(), state, rules)

        assert len(fills) == 1
        assert fills[0].price == pytest.approx(fill_price, abs=1e-9)
        assert fills[0].fee == pytest.approx(fee, abs=1e-9)
        portfolio.apply_fill(fills[0])
        assert portfolio.cash == pytest.approx(final_cash, abs=1e-9)

    def test_tightening_the_band_saves_the_locked_queue_width(self) -> None:
        """5% vs 2% band on the same locked order: 3,003 less paid."""
        paid = {}
        for limit_pct in (0.05, 0.02):
            rules = TSERulesEngine(limit_pct=limit_pct)
            _, up = rules.compute_price_limits(1_000.0)
            state = _state(close=up, limit_up=up, ask_size=0.0, ask_queue=100.0, bid_queue=0.0)
            engine = _engine()
            portfolio = PortfolioEngine(initial_cash=CASH)
            engine.submit(_buy(100.0))
            for fill in engine.match(_tick(), state, rules):
                portfolio.apply_fill(fill)
            paid[limit_pct] = CASH - portfolio.cash

        # 105_105 at +5% versus 102_102 at +2% — 30/unit price plus 3 of fee.
        assert paid[0.05] == pytest.approx(105_105.0)
        assert paid[0.02] == pytest.approx(102_102.0)
        assert paid[0.05] - paid[0.02] == pytest.approx(3_003.0)

    def test_tightening_the_band_does_not_rescue_a_queued_buy(self) -> None:
        """Queue position, not the band, gates a locked-buy fill."""
        rules = TSERulesEngine(limit_pct=0.02)
        _, up = rules.compute_price_limits(1_000.0)
        # 5,000 ahead in the bid queue; 70% of the 100 traded volume clears the
        # limit plus 5% cancellations = 250 → 4,680 still queued → no fill.
        state = _state(close=up, limit_up=up, ask_size=0.0, ask_queue=100.0, bid_queue=5_000.0, volume=100.0)

        engine = _engine()
        order = _buy(100.0)
        engine.submit(order)
        assert engine.match(_tick(), state, rules) == []
        assert order.remaining_qty == pytest.approx(100.0)
        assert engine.queue_positions[order.order_id] == pytest.approx(4_680.0)


# ── 2. Trade cancellation ─────────────────────────────────────────────────


class TestTradeCancellation:
    def test_cancel_before_match_leaves_the_book_untouched(self) -> None:
        rules = TSERulesEngine()
        engine = _engine()
        portfolio = PortfolioEngine(initial_cash=CASH)
        order = _buy(100.0, price=1_000.0)
        engine.submit(order)
        assert order.status is OrderStatus.ACKED

        engine.cancel_all()
        fills = engine.match(_tick(), _state(), rules)

        assert fills == []
        assert order.status is OrderStatus.CANCELLED
        assert engine.live_orders == []
        assert portfolio.cash == pytest.approx(CASH)  # no cost was incurred
        assert portfolio.positions == {}

    def test_cancel_without_a_prior_submit_is_a_no_op(self) -> None:
        engine = _engine()
        engine.cancel_all()
        assert engine.live_orders == []
        assert engine.all_orders == []

    def test_partial_fill_then_cancel_freezes_only_the_remaining_qty(self) -> None:
        """Ask depth 40 fills 40 now; the cancel strands the other 60."""
        rules = TSERulesEngine()
        engine = _engine()
        portfolio = PortfolioEngine(initial_cash=CASH)
        order = _buy(100.0)
        engine.submit(order)

        # cost = 40 * 1000 + fee(40 * 1000 * 0.001 = 40) = 40_040
        fills = engine.match(_tick(), _state(ask_size=40.0), rules)
        assert len(fills) == 1
        assert fills[0].qty == pytest.approx(40.0)
        assert fills[0].fee == pytest.approx(40.0)
        assert order.status is OrderStatus.PARTIAL_FILL
        assert order.remaining_qty == pytest.approx(60.0)
        portfolio.apply_fill(fills[0])
        assert portfolio.cash == pytest.approx(CASH - 40_040.0)

        engine.cancel_all()
        assert order.status is OrderStatus.CANCELLED
        assert engine.match(_tick(), _state(), rules) == []
        # the cancelled remainder never trades
        assert portfolio.cash == pytest.approx(CASH - 40_040.0)
        assert portfolio.positions[SYMBOL].qty == pytest.approx(40.0)

    def test_cancelled_orders_are_dropped_from_the_next_match(self) -> None:
        rules = TSERulesEngine()
        engine = _engine()
        first = _buy(10.0, order_id="B1")
        engine.submit(first)
        engine.cancel_all()
        second = _buy(20.0, order_id="B2")
        engine.submit(second)

        fills = engine.match(_tick(), _state(), rules)

        # Only the live order fills: 20 * 1000 + fee 20 = 20_020.
        assert [f.order_id for f in fills] == ["B2"]
        assert fills[0].qty == pytest.approx(20.0)
        assert first.status is OrderStatus.CANCELLED


# ── 3. Symbol halt / resume ───────────────────────────────────────────────


class TestSymbolHalt:
    """The halt gate is ``TSERulesEngine.can_trade``, reached through ``run`` too.

    STEP 7D-2 wired ``MarketState.is_halted`` into
    ``EventBacktestEngine.run`` (``bar["is_halted"]``), so the end-to-end class
    below drives the whole engine; the component cases still pin the rules and
    execution boundary the engine relies on.
    """

    def test_can_trade_is_false_while_halted(self) -> None:
        assert TSERulesEngine().can_trade(_state(is_halted=True)) is False

    def test_can_trade_is_false_without_a_price(self) -> None:
        assert TSERulesEngine().can_trade(_state(close=0.0)) is False

    def test_halted_symbol_never_fills_and_never_moves_cash(self) -> None:
        rules = TSERulesEngine()
        engine = _engine()
        portfolio = PortfolioEngine(initial_cash=CASH)
        order = _buy(100.0)
        engine.submit(order)

        fills = engine.match(_tick(), _state(is_halted=True), rules)

        assert fills == []
        assert order.status is OrderStatus.ACKED
        assert order.remaining_qty == pytest.approx(100.0)
        assert portfolio.cash == pytest.approx(CASH)

    def test_resume_after_halt_fills_at_the_resumed_price(self) -> None:
        rules = TSERulesEngine()
        engine = _engine()
        portfolio = PortfolioEngine(initial_cash=CASH)
        order = _buy(100.0)
        engine.submit(order)

        assert engine.match(_tick(), _state(is_halted=True), rules) == []
        # Resumed 2% above the pre-halt close: price = ask 1020,
        # cost = 100 * 1020 + fee(100 * 1020 * 0.001 = 102) = 102_102.
        fills = engine.match(_tick(), _state(is_halted=False, ask_price=1_020.0, close=1_020.0), rules)

        assert len(fills) == 1
        assert fills[0].price == pytest.approx(1_020.0)
        assert fills[0].fee == pytest.approx(102.0)
        portfolio.apply_fill(fills[0])
        assert portfolio.cash == pytest.approx(CASH - 102_102.0)
        assert portfolio.positions[SYMBOL].qty == pytest.approx(100.0)

    def test_halt_blocks_the_sell_exit_too(self) -> None:
        rules = TSERulesEngine()
        engine = _engine()
        portfolio = PortfolioEngine(initial_cash=CASH)
        buy = _buy(100.0)
        engine.submit(buy)
        for fill in engine.match(_tick(), _state(), rules):
            portfolio.apply_fill(fill)
        cash_after_entry = portfolio.cash
        assert cash_after_entry == pytest.approx(CASH - 100_100.0)

        sell = _sell(100.0, price=1_100.0)
        engine.submit(sell)
        assert engine.match(_tick(), _state(is_halted=True, bid_price=1_100.0), rules) == []
        assert portfolio.cash == pytest.approx(cash_after_entry)

        fills = engine.match(_tick(), _state(bid_price=1_100.0), rules)
        # proceeds = 100 * 1100 - fee(110) - tax(100 * 1100 * 0.001 = 110)
        assert fills[0].price == pytest.approx(1_100.0)
        assert fills[0].fee == pytest.approx(110.0)
        assert fills[0].tax == pytest.approx(110.0)
        portfolio.apply_fill(fills[0])
        assert portfolio.cash == pytest.approx(cash_after_entry + 109_780.0)


# ── 4. Physical delivery cost ─────────────────────────────────────────────


class TestPhysicalDeliveryCost:
    """Delivery cost enters through the commission knobs of ``ExecutionEngine``.

    ``commission_buy`` / ``commission_sell`` are the existing extension point, so
    a bullion/delivery surcharge is modelled as a rate overlay rather than a new
    engine concept.
    """

    BASE_RATE = 0.001
    PRICE = 1_000_000.0
    QTY = 10.0
    NOTIONAL = 10_000_000.0  # 10 * 1_000_000

    @pytest.mark.parametrize(
        ("delivery_bps", "rate", "fee", "cash_after_buy"),
        [
            (0, 0.0010, 10_000.0, 989_990_000.0),
            (25, 0.0035, 35_000.0, 989_965_000.0),
            (60, 0.0070, 70_000.0, 989_930_000.0),
        ],
    )
    def test_entry_cost_grows_with_the_delivery_surcharge(
        self, delivery_bps, rate, fee, cash_after_buy
    ) -> None:
        assert self.BASE_RATE + delivery_bps / 10_000 == pytest.approx(rate, abs=1e-12)

        rules = TSERulesEngine()
        engine = _engine(commission_buy=rate, commission_sell=rate)
        portfolio = PortfolioEngine(initial_cash=1_000_000_000.0)
        engine.submit(_buy(self.QTY, price=self.PRICE))

        fills = engine.match(_tick(), _state(close=self.PRICE, ask_price=self.PRICE), rules)

        assert len(fills) == 1
        # fee = qty * price * rate = 10 * 1e6 * rate
        assert fills[0].fee == pytest.approx(fee, abs=1e-9)
        portfolio.apply_fill(fills[0])
        assert portfolio.cash == pytest.approx(cash_after_buy, abs=1e-9)
        assert portfolio.total_fees == pytest.approx(fee, abs=1e-9)

    def test_delivery_cost_is_charged_on_the_exit_as_well_as_the_entry(self) -> None:
        rate = 0.0035  # 0.10% commission + 0.25% delivery
        rules = TSERulesEngine()
        engine = _engine(commission_buy=rate, commission_sell=rate)
        portfolio = PortfolioEngine(initial_cash=1_000_000_000.0)
        state = _state(close=self.PRICE, ask_price=self.PRICE, bid_price=self.PRICE)

        buy = _buy(self.QTY, price=self.PRICE)
        engine.submit(buy)
        for fill in engine.match(_tick(), state, rules):
            portfolio.apply_fill(fill)

        sell = _sell(self.QTY, price=self.PRICE)
        engine.submit(sell)
        exit_fills = engine.match(_tick(), state, rules)

        assert len(exit_fills) == 1
        # exit: proceeds = notional - fee(35_000) - tax(notional * 0.001 = 10_000)
        assert exit_fills[0].fee == pytest.approx(35_000.0, abs=1e-9)
        assert exit_fills[0].tax == pytest.approx(10_000.0, abs=1e-9)
        portfolio.apply_fill(exit_fills[0])

        # Round trip: -10_035_000 entry, +9_955_000 exit → 80_000 total cost
        # (two 35_000 commissions + one 10_000 tax).
        assert portfolio.cash == pytest.approx(1_000_000_000.0 - 80_000.0, abs=1e-9)
        assert portfolio.total_fees == pytest.approx(70_000.0, abs=1e-9)
        assert portfolio.total_taxes == pytest.approx(10_000.0, abs=1e-9)
        assert portfolio.positions[SYMBOL].qty == pytest.approx(0.0)

    def test_slippage_compounds_on_top_of_the_delivery_rate(self) -> None:
        """Fixed-basis-point slippage lifts the price, and the fee follows it."""
        rules = TSERulesEngine()
        engine = _engine(
            commission_buy=0.0035,
            slippage_model=SlippageModel(model_type="fixed", fixed_bps=100.0),
        )
        portfolio = PortfolioEngine(initial_cash=1_000_000_000.0)
        engine.submit(_buy(self.QTY, price=self.PRICE))

        fills = engine.match(_tick(), _state(close=self.PRICE, ask_price=self.PRICE), rules)

        # 100 bps = 1.0% on the 1,000,000 offer → fill price 1,010,000;
        # fee = 10 * 1,010,000 * 0.0035 = 35,350.
        assert fills[0].price == pytest.approx(1_010_000.0, abs=1e-9)
        assert fills[0].fee == pytest.approx(35_350.0, abs=1e-9)
        portfolio.apply_fill(fills[0])
        assert portfolio.cash == pytest.approx(1_000_000_000.0 - (10_100_000.0 + 35_350.0), abs=1e-9)


# ── 5. Margin stop-out ────────────────────────────────────────────────────


class TestMarginStopOut:
    def test_long_losing_path_hits_margin_call_then_stop_out(self) -> None:
        # starting equity = initial margin = 4000 * 100 * 0.2 = 80_000
        result = simulate_margin_path(
            4_000.0, [4_000, 3_950, 3_500, 3_400, 3_300], direction=1, quantity=1.0,
            config=MARGIN_CONFIG,
        )

        assert result["status"] == "ok"
        assert result["starting_equity"] == pytest.approx(80_000.0)
        assert result["initial_margin_requirement"] == pytest.approx(80_000.0)

        steps = result["steps"]
        # index 0: pnl 0 → equity 80_000 / maintenance 40_000 = 2.0 → no event
        assert steps[0]["equity"] == pytest.approx(80_000.0)
        assert steps[0]["equity_ratio"] == pytest.approx(2.0)
        assert steps[0]["event"] is None
        # index 1: pnl -5_000 → 75_000 / 39_500 = 1.898734 → no event
        assert steps[1]["pnl"] == pytest.approx(-5_000.0)
        assert steps[1]["event"] is None
        # index 2: pnl -50_000 → 30_000 / 35_000 = 0.857143 → MARGIN_CALL
        assert steps[2]["equity"] == pytest.approx(30_000.0)
        assert steps[2]["equity_ratio"] == pytest.approx(0.857142857, abs=1e-6)
        assert steps[2]["event"] == "MARGIN_CALL"
        # index 3: pnl -60_000 → 20_000 / 34_000 = 0.588235 → still a call
        assert steps[3]["event"] == "MARGIN_CALL"
        # index 4: pnl -70_000 → 10_000 / 33_000 = 0.303030 → STOP_OUT
        assert steps[4]["equity"] == pytest.approx(10_000.0)
        assert steps[4]["event"] == "STOP_OUT"

        assert result["margin_call"] is True
        assert result["margin_call_index"] == 2
        assert result["stop_out"] is True
        assert result["stop_out_index"] == 4
        assert result["final_equity"] == pytest.approx(10_000.0)

    def test_short_position_stops_out_on_a_rally(self) -> None:
        result = simulate_margin_path(
            4_000.0, [4_000, 4_050, 4_500], direction=-1, quantity=1.0, config=MARGIN_CONFIG
        )

        steps = result["steps"]
        # index 1: pnl = (4050-4000) * -1 * 100 = -5_000 → 75_000 / 40_500
        assert steps[1]["pnl"] == pytest.approx(-5_000.0)
        assert steps[1]["equity_ratio"] == pytest.approx(75_000.0 / 40_500.0, abs=1e-9)
        assert steps[1]["event"] is None
        # index 2: pnl = -50_000 → 30_000 / 45_000 = 0.6667 → call, above the 0.5 stop
        assert steps[2]["equity"] == pytest.approx(30_000.0)
        assert steps[2]["event"] == "MARGIN_CALL"
        assert result["margin_call_index"] == 2
        assert result["stop_out"] is False
        assert result["stop_out_index"] is None

    @pytest.mark.parametrize(
        ("prices", "expected_call", "expected_stop"),
        [
            ([4_000, 3_990], False, False),  # equity 79_000 / 39_900 = 1.98
            ([4_000, 3_900], False, False),  # equity 70_000 / 39_000 = 1.79
            ([4_000, 3_500], True, False),  # 0.857 → call only
            # A single step straight through the call level only ever records a
            # stop-out: the engine classifies each step as at most one event.
            ([4_000, 3_300], False, True),  # 0.303 → STOP_OUT, never a call
            ([4_000, 3_500, 3_300], True, True),  # call at 1, stop-out at 2
        ],
    )
    def test_adverse_move_depth_decides_the_event(self, prices, expected_call, expected_stop) -> None:
        result = simulate_margin_path(
            4_000.0, prices, direction=1, quantity=1.0, config=MARGIN_CONFIG
        )

        assert result["margin_call"] is expected_call
        assert result["stop_out"] is expected_stop

    def test_extra_quantity_brings_the_stop_out_closer(self) -> None:
        """2 contracts doubles the loss per point, so a shallower drop stops out."""
        # entry 4000, qty 2 → initial margin 160_000; at 3600:
        # pnl = -400 * 2 * 100 = -80_000 → equity 80_000; maintenance = 3600*200*0.1 = 72_000
        # ratio = 1.111 → still fine.  At 3400: pnl -120_000 → 40_000 / 68_000 = 0.588 → call.
        # At 3300: pnl -140_000 → 20_000 / 66_000 = 0.303 → stop-out.
        result = simulate_margin_path(
            4_000.0, [4_000, 3_600, 3_400, 3_300], direction=1, quantity=2.0, config=MARGIN_CONFIG
        )

        assert result["initial_margin_requirement"] == pytest.approx(160_000.0)
        assert result["steps"][1]["event"] is None
        assert result["steps"][2]["event"] == "MARGIN_CALL"
        assert result["steps"][3]["event"] == "STOP_OUT"
        assert result["stop_out_index"] == 3

    def test_missing_configuration_is_reported_not_guessed(self) -> None:
        partial = {k: v for k, v in MARGIN_CONFIG.items() if k != "stop_out_equity_ratio"}
        result = simulate_margin_path(
            4_000.0, [4_000, 3_300], config=partial
        )

        assert result["status"] == "not_configured"
        assert result["configured"] is False
        assert result["missing"] == ["stop_out_equity_ratio"]
        assert result["steps"] == []
        assert result["stop_out"] is False

    def test_every_required_key_is_reported_when_config_is_empty(self) -> None:
        result = simulate_margin_path(4_000.0, [4_000], config={})

        assert result["status"] == "not_configured"
        assert result["missing"] == list(REQUIRED_MARGIN_KEYS)

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"entry_price": 0.0, "prices": [4_000]}, "entry_price must be positive"),
            ({"entry_price": 4_000.0, "prices": []}, "prices must not be empty"),
            ({"entry_price": 4_000.0, "prices": [0.0]}, "prices must be positive"),
            ({"entry_price": 4_000.0, "prices": [4_000], "direction": 0}, "direction must be 1 or -1"),
            ({"entry_price": 4_000.0, "prices": [4_000], "quantity": 0.0}, "quantity must be positive"),
        ],
    )
    def test_invalid_inputs_are_rejected(self, kwargs, message) -> None:
        with pytest.raises(ValueError, match=message):
            simulate_margin_path(config=MARGIN_CONFIG, **kwargs)

    def test_stop_out_ratio_above_margin_call_ratio_is_rejected(self) -> None:
        bad = dict(MARGIN_CONFIG, margin_call_equity_ratio=0.4, stop_out_equity_ratio=0.9)
        with pytest.raises(ValueError, match="stop_out_equity_ratio must not exceed"):
            simulate_margin_path(4_000.0, [4_000], config=bad)


# ── 3b. Symbol halt, end to end through EventBacktestEngine.run (STEP 7D-2) ─


def _engine_bars(*, halt_second_bar: bool) -> list[dict[str, float | bool | str]]:
    """Bar 0 trades; bar 1 is the same market with/without ``is_halted``."""
    bars: list[dict[str, float | bool | str]] = []
    for index, close in enumerate((1_000.0, 1_030.0)):
        bar: dict[str, float | bool | str] = {
            "symbol": "A",
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": 10_000_000.0,
            "value": close * 10_000_000.0,
            "bid_price": close,
            "ask_price": close,
            "bid_size": 1_000_000.0,
            "ask_size": 1_000_000.0,
            "yesterday_close": 1_000.0,
        }
        if index == 1 and halt_second_bar:
            bar["is_halted"] = True
        bars.append(bar)
    return bars


class TestHaltEndToEnd:
    """``run`` must read ``bar["is_halted"]`` and refuse to trade that bar."""

    INITIAL_CASH = 1_000_000_000.0
    # Hand-computed entry size: int(1e9 * 0.20 max-position / 1000 close).
    EXPECTED_QTY = 200_000

    def test_halted_bar_blocks_the_exit_and_freezes_nav(self) -> None:
        engine = EventBacktestEngine(initial_cash=self.INITIAL_CASH)
        report = engine.run(_engine_bars(halt_second_bar=True), [1, -1])

        # The buy on bar 0 fills; the sell on the halted bar is never even
        # submitted, so nav cannot move on it.
        assert report["trading"]["total_trades"] == 0
        assert len(engine.execution.all_orders) == 1
        assert engine.portfolio.positions["A"].qty == pytest.approx(self.EXPECTED_QTY)
        curve = engine.portfolio.equity_curve
        assert curve[1]["nav"] == curve[0]["nav"]

    def test_identical_bar_without_the_halt_closes_the_position(self) -> None:
        """Control: only ``is_halted`` differs between the two runs."""
        engine = EventBacktestEngine(initial_cash=self.INITIAL_CASH)
        report = engine.run(_engine_bars(halt_second_bar=False), [1, -1])

        assert report["trading"]["total_trades"] == 1
        assert len(engine.execution.all_orders) == 2
        assert engine.portfolio.positions["A"].qty == pytest.approx(0.0)
        curve = engine.portfolio.equity_curve
        assert curve[1]["nav"] != curve[0]["nav"]

    def test_absent_is_halted_key_keeps_the_old_behaviour(self) -> None:
        """A bar without the key trades normally — the wiring adds no default halt."""
        bars = _engine_bars(halt_second_bar=False)
        assert all("is_halted" not in bar for bar in bars)

        engine = EventBacktestEngine(initial_cash=self.INITIAL_CASH)
        engine.run(bars, [1, -1])

        assert engine.portfolio.positions["A"].qty == pytest.approx(0.0)
