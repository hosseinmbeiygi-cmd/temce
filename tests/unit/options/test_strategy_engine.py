"""Tests for the strategy-engine extensions (spec §5.2, §7.2-7.11)."""

from __future__ import annotations

import math

import pytest

from domain.options.payoff import OptionLeg
from domain.options.symbol_parser import (
    OptionSymbolError,
    is_option_symbol,
    parse_option_symbol,
    parse_or_none,
)
from domain.options.strategy_engine import (
    AdjustmentEngine,
    ChainQuote,
    GreeksAggregator,
    InMemoryChainLookup,
    StrategyLifecycleTracker,
    StrategyStatus,
    StrategyTemplateLibrary,
    StrategyValidator,
    TemplateLeg,
)
from domain.options.signals import PositionSizer, RuleEngine, SignalGenerator


# ── Symbol parser (§5.2) ─────────────────────────────────────────────────


class TestSymbolParser:
    def test_persian_tal_call(self):
        parsed = parse_option_symbol("خودروط600001001")
        assert parsed.base_symbol == "خودرو"
        assert parsed.option_type == "CALL"
        assert parsed.strike == 600001001.0

    def test_delimited_form(self):
        parsed = parse_option_symbol("فولاد-ط-6000-20260921")
        assert parsed.base_symbol == "فولاد"
        assert parsed.option_type == "CALL"
        assert parsed.strike == 6000.0
        assert parsed.expiry == "20260921"

    def test_tahod_put(self):
        parsed = parse_option_symbol("فولادت45000")
        assert parsed.option_type == "PUT"
        assert parsed.strike == 45000.0

    def test_latin_call_put(self):
        assert parse_option_symbol("FOLAD-C-6000").option_type == "CALL"
        assert parse_option_symbol("FOLAD-P-6000").option_type == "PUT"

    def test_persian_digits(self):
        parsed = parse_option_symbol("فولادط۶۰۰۰")
        assert parsed.strike == 6000.0

    def test_zwnj_stripped(self):
        parsed = parse_option_symbol("خودرو\u200cط6000")
        assert parsed.base_symbol == "خودرو"
        assert parsed.option_type == "CALL"

    def test_invalid_no_type(self):
        with pytest.raises(OptionSymbolError):
            parse_option_symbol("فولاد6000")

    def test_invalid_empty(self):
        with pytest.raises(OptionSymbolError):
            parse_option_symbol("")

    def test_is_option_symbol(self):
        assert is_option_symbol("خودروط600001001") is True
        assert is_option_symbol("فولاد") is False

    def test_parse_or_none(self):
        assert parse_or_none("فولاد") is None
        assert parse_or_none("فولادط6000").strike == 6000.0


# ── Chain lookup + templates (§7.9) ──────────────────────────────────────


def _chain() -> InMemoryChainLookup:
    quotes = []
    expiries = ["2026-10-20", "2026-11-17"]
    strikes = [37000, 38500, 40000, 43000, 46000]
    for expiry in expiries:
        for k in strikes:
            call_delta = max(0.02, min(0.98, 0.5 + (40000 - k) / 12000))
            put_delta = -call_delta
            quotes.append(
                ChainQuote(
                    option_type="call",
                    strike=k,
                    expiry=expiry,
                    premium=max(k - 40000, 0) + 2000,
                    delta=call_delta,
                    open_interest=500,
                )
            )
            quotes.append(
                ChainQuote(
                    option_type="put",
                    strike=k,
                    expiry=expiry,
                    premium=max(40000 - k, 0) + 2000,
                    delta=put_delta,
                    open_interest=500,
                )
            )
    return InMemoryChainLookup(quotes, spot=40000)


class TestChainLookup:
    def test_nearest_strike(self):
        chain = _chain()
        assert chain.nearest_strike(40200, "call", "2026-10-20") == 40000

    def test_nearest_expiry(self):
        chain = _chain()
        assert chain.nearest_expiry(25) in {"2026-10-20", "2026-11-17"}

    def test_strike_for_delta(self):
        chain = _chain()
        k = chain.strike_for_delta(0.30, "call", "2026-10-20")
        assert k == 43000  # delta declines as strike rises above spot

    def test_empty_chain_raises(self):
        chain = InMemoryChainLookup([], spot=1.0)
        with pytest.raises(ValueError):
            chain.nearest_strike(100, "call", "2026-01-01")


class TestTemplateLibrary:
    def test_available_templates(self):
        lib = StrategyTemplateLibrary(_chain())
        for name in ("COVERED_CALL", "IRON_CONDOR", "COLLAR", "JADE_LIZARD", "CALENDAR_SPREAD"):
            assert name in lib.available()

    def test_unknown_template(self):
        lib = StrategyTemplateLibrary(_chain())
        with pytest.raises(ValueError):
            lib.build("NOPE")

    def test_covered_call_has_stock_and_short_call(self):
        lib = StrategyTemplateLibrary(_chain())
        built = lib.build("COVERED_CALL")
        assert built.legs[0].option_type == "stock"
        assert built.legs[1].action == "sell"
        assert built.legs[1].strike > lib.chain.spot

    def test_iron_condor_four_legs(self):
        lib = StrategyTemplateLibrary(_chain())
        built = lib.build("IRON_CONDOR", short_delta=0.25)
        assert len(built.legs) == 4
        actions = {leg.action for leg in built.legs}
        assert actions == {"buy", "sell"}
        puts = [leg for leg in built.legs if leg.option_type == "put"]
        calls = [leg for leg in built.legs if leg.option_type == "call"]
        assert puts[0].strike > puts[1].strike  # short put above long put
        assert calls[0].strike < calls[1].strike  # short call below long call

    def test_collar(self):
        lib = StrategyTemplateLibrary(_chain())
        built = lib.build("COLLAR")
        kinds = [leg.option_type for leg in built.legs]
        assert kinds == ["stock", "put", "call"]
        actions = [leg.action for leg in built.legs]
        assert actions == ["buy", "buy", "sell"]

    def test_payoff_legs_valid(self):
        lib = StrategyTemplateLibrary(_chain())
        built = lib.build("BULL_CALL_SPREAD")
        assert all(isinstance(leg, OptionLeg) for leg in built.payoff_legs)


# ── Greeks aggregator + dual payoff (§7.2) ───────────────────────────────


class TestGreeksAggregator:
    def test_stock_only_delta(self):
        agg = GreeksAggregator()
        legs = [TemplateLeg("stock", "buy", None, 100.0, 1.0)]
        value, greeks = agg.portfolio_value_and_greeks(legs, spot=100.0, days_to_expiry=30)
        assert math.isclose(value, 100.0)
        assert math.isclose(greeks["delta"], 1.0)

    def test_short_call_negative_delta(self):
        agg = GreeksAggregator()
        legs = [TemplateLeg("call", "sell", 105.0, 2.0, 1.0)]
        _, greeks = agg.portfolio_value_and_greeks(legs, spot=100.0, days_to_expiry=30)
        assert greeks["delta"] < 0
        assert greeks["theta"] > 0  # short options collect theta

    def test_dual_payoff_curve_shape(self):
        agg = GreeksAggregator()
        legs = [
            TemplateLeg("stock", "buy", None, 100.0, 1.0),
            TemplateLeg("call", "sell", 110.0, 2.0, 1.0),
        ]
        curve = agg.dual_payoff_curve(legs, spot=100.0, days_to_expiry=30, price_min=80, price_max=130, step=5)
        assert len(curve) == 11
        first = curve[0]
        assert {"price", "payoff", "current_value"} <= set(first)
        # Expiry payoff of covered call at 80: 80-100 + 2 = -18
        assert math.isclose(first["payoff"], -18.0, rel_tol=1e-6)


# ── Validator (§7.10) ─────────────────────────────────────────────────────


class TestValidator:
    def test_empty_legs_rejected(self):
        errors = StrategyValidator().validate([])
        assert not errors[0].find("بدون پایه") == -1

    def test_low_oi_flagged(self):
        chain = InMemoryChainLookup(
            [ChainQuote("call", 40000, "2026-10-20", 2000, delta=0.4, open_interest=2)],
            spot=40000,
        )
        legs = [TemplateLeg("call", "buy", 40000, 2000, 1.0, "2026-10-20")]
        errors = StrategyValidator().validate(legs, chain=chain)
        assert any("نقدشوندگی" in e for e in errors)

    def test_margin_exceeds_cash(self):
        legs = [TemplateLeg("put", "sell", 38000, 1500, 1.0, "2026-10-20")]
        errors = StrategyValidator().validate(
            legs, portfolio_state={"available_cash": 1_000_000}, estimated_margin=2_000_000
        )
        assert any("وجه تضمین" in e for e in errors)

    def test_concentration_limit(self):
        legs = [TemplateLeg("call", "buy", 41000, 2200, 1.0, "2026-10-20")]
        errors = StrategyValidator().validate(
            legs,
            portfolio_state={"current_concentration": 0.2, "new_concentration": 0.1},
            user_limits={"max_concentration_pct": 0.25},
        )
        assert any("تمرکز" in e for e in errors)

    def test_clean_strategy_passes(self):
        legs = [TemplateLeg("call", "buy", 40000, 2000, 1.0, "2026-10-20")]
        chain = InMemoryChainLookup(
            [ChainQuote("call", 40000, "2026-10-20", 2000, delta=0.5, open_interest=100)],
            spot=40000,
        )
        errors = StrategyValidator().validate(legs, chain=chain)
        assert errors == []


# ── Adjustment engine (§7.6) ──────────────────────────────────────────────


class TestAdjustmentEngine:
    def test_roll_forward(self):
        engine = AdjustmentEngine()
        out = engine.evaluate(
            {"days_to_expiry": 3, "unrealized_pnl_pct": 15},
            {},
        )
        assert any(s["action"] == "ROLL_FORWARD" for s in out)

    def test_defend_side(self):
        out = AdjustmentEngine().evaluate(
            {"days_to_expiry": 20, "threatened_leg": "short_call", "distance_to_threatened_strike_pct": 1.2},
            {},
        )
        assert any(s["action"] == "DEFEND_SIDE" for s in out)

    def test_delta_hedge(self):
        out = AdjustmentEngine().evaluate(
            {"days_to_expiry": 20, "portfolio_delta": 350, "user_delta_limit": 200},
            {},
        )
        assert any(s["action"] == "DELTA_HEDGE" for s in out)

    def test_quiet_market(self):
        out = AdjustmentEngine().evaluate({"days_to_expiry": 25, "unrealized_pnl_pct": -5}, {})
        assert out == []


# ── Lifecycle (§7.7) ──────────────────────────────────────────────────────


class TestLifecycle:
    def test_happy_path(self):
        tracker = StrategyLifecycleTracker()
        tracker.create("s1")
        tracker.transition("s1", StrategyStatus.PENDING_APPROVAL)
        tracker.transition("s1", StrategyStatus.PENDING_EXECUTION)
        tracker.transition("s1", StrategyStatus.ACTIVE)
        tracker.transition("s1", StrategyStatus.CLOSED)
        assert tracker.status("s1") is StrategyStatus.CLOSED

    def test_invalid_transition(self):
        tracker = StrategyLifecycleTracker()
        tracker.create("s2")
        with pytest.raises(ValueError):
            tracker.transition("s2", StrategyStatus.ACTIVE)  # must pass approval+execution

    def test_unknown_strategy(self):
        with pytest.raises(KeyError):
            StrategyLifecycleTracker().transition("ghost", StrategyStatus.CLOSED)


# ── Signal generator (§7.3) ───────────────────────────────────────────────


class TestSignalGenerator:
    def test_high_iv_sells_premium(self):
        out = SignalGenerator().score(
            {"iv_rank": 85, "trend_strength": 0.0, "days_to_expiry": 30}
        )
        assert out["suggestion"] == "SELL_PREMIUM"

    def test_low_iv_with_trend_buys(self):
        out = SignalGenerator().score(
            {"iv_rank": 15, "trend_strength": 0.8, "days_to_expiry": 30}
        )
        assert out["suggestion"] == "BUY_DIRECTIONAL"

    def test_neutral_middle(self):
        out = SignalGenerator().score({"iv_rank": 50, "trend_strength": 0.1, "days_to_expiry": 30})
        assert out["suggestion"] == "NEUTRAL_WAIT"

    def test_dte_factor_outside_window(self):
        in_window = SignalGenerator().score({"iv_rank": 85, "days_to_expiry": 30})
        out_window = SignalGenerator().score({"iv_rank": 85, "days_to_expiry": 3})
        assert out_window["score"] < in_window["score"]

    def test_ml_probability_is_weighted_feature(self):
        base = {"iv_rank": 50, "trend_strength": 0.0, "days_to_expiry": 30}
        with_ml = SignalGenerator().score({**base, "ml_probability": 0.95})
        without_ml = SignalGenerator().score(base)
        assert with_ml["score"] > without_ml["score"]

    def test_score_bounded(self):
        out = SignalGenerator().score({"iv_rank": 100, "skew": 5, "trend_strength": 1, "days_to_expiry": 30})
        assert 0.0 <= out["score"] <= 1.0


# ── Position sizer (§7.4) ─────────────────────────────────────────────────


class TestPositionSizer:
    def test_fixed_fractional(self):
        out = PositionSizer(method="fractional_fixed", risk_per_trade_pct=1.0).size(
            capital=10_000_000, max_loss_per_contract=50_000
        )
        assert out["contracts"] == 2  # 1% of 10M = 100k / 50k

    def test_kelly_capped(self):
        out = PositionSizer(method="kelly", kelly_cap_pct=25.0).size(
            capital=10_000_000,
            max_loss_per_contract=100_000,
            win_rate=0.6,
            win_loss_ratio=1.5,
        )
        kelly = 0.6 - 0.4 / 1.5  # ≈ 0.3333 → capped at 25 %
        assert out["kelly_fraction"] == 0.25
        assert out["contracts"] == 25  # 2.5M / 100k

    def test_kelly_requires_stats(self):
        with pytest.raises(ValueError):
            PositionSizer(method="kelly").size(capital=1_000, max_loss_per_contract=100)

    def test_zero_max_loss(self):
        out = PositionSizer().size(capital=1_000_000, max_loss_per_contract=0)
        assert out["contracts"] == 0

    def test_invalid_method(self):
        with pytest.raises(ValueError):
            PositionSizer(method="martingale").size(capital=1_000, max_loss_per_contract=10)


# ── Rule engine DSL (§7.5) ────────────────────────────────────────────────


SPEC = {
    "entry": {
        "all_of": [
            {"iv_rank": {"gt": 70}},
            {"days_to_expiry": {"between": [20, 45]}},
            {"underlying_trend": {"eq": "RANGE_BOUND"}},
        ]
    },
    "exit": {
        "any_of": [
            {"profit_target_pct": {"gte": 50}},
            {"stop_loss_pct": {"gte": 100}},
            {"days_to_expiry": {"lt": 5}},
        ],
        "scale_out": [
            {"at_profit_pct": 30, "close_fraction": 0.5},
            {"at_profit_pct": 50, "close_fraction": 1.0},
        ],
    },
}


class TestRuleEngine:
    def test_entry_all_conditions_met(self):
        engine = RuleEngine(SPEC)
        assert engine.should_enter(
            {"iv_rank": 80, "days_to_expiry": 30, "underlying_trend": "RANGE_BOUND"}
        )

    def test_entry_blocked_when_one_fails(self):
        engine = RuleEngine(SPEC)
        assert not engine.should_enter(
            {"iv_rank": 80, "days_to_expiry": 10, "underlying_trend": "RANGE_BOUND"}
        )

    def test_exit_on_profit_target(self):
        engine = RuleEngine(SPEC)
        actions = engine.exit_actions({"profit_target_pct": 55, "days_to_expiry": 20})
        assert actions["exit_triggered"] is True
        assert actions["close_fraction"] == 1.0

    def test_scale_out_partial(self):
        engine = RuleEngine(SPEC)
        actions = engine.exit_actions({"profit_pct": 35, "days_to_expiry": 20})
        assert actions["scale_out"]["close_fraction"] == 0.5
        assert actions["close_fraction"] == 0.5

    def test_no_exit_when_flat(self):
        engine = RuleEngine(SPEC)
        actions = engine.exit_actions({"profit_pct": 5, "days_to_expiry": 20})
        assert actions["exit_triggered"] is False

    def test_nested_any_of(self):
        spec = {"entry": {"any_of": [{"all_of": [{"a": {"gt": 1}}, {"b": {"gt": 1}}]}, {"c": {"eq": 5}}]}}
        engine = RuleEngine(spec)
        assert engine.should_enter({"a": 2, "b": 2})
        assert engine.should_enter({"c": 5})
        assert not engine.should_enter({"a": 2, "b": 0, "c": 1})

    def test_unknown_operator_raises(self):
        with pytest.raises(ValueError):
            RuleEngine({"entry": {"x": {"yolo": 1}}}).should_enter({"x": 1})

    def test_empty_spec_enters(self):
        assert RuleEngine({}).should_enter({}) is True
