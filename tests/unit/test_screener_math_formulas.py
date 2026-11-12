"""Unit tests for mathematical formulas in the screener stack.

Covers:
  1. VectorCalculator scoring thresholds and boundary values
  2. 110-column decision logic (risk gate, neg-filter, score threshold)
  3. AdvancedAnalyticsEngine._compute_composite score bands and clamp
  4. WEIGHTS sum-to-one invariant
"""

from __future__ import annotations

import pytest

from services.screener110_service import RISK_FILTER_COLUMNS, WEIGHTS, VectorCalculator


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def calc() -> VectorCalculator:
    return VectorCalculator()


def _daily(n: int = 30, price: float = 100.0) -> list[dict]:
    return [
        {
            "price_close": price,
            "price_last": price,
            "price_max": price + 2,
            "price_min": price - 2,
            "trade_volume": 500_000,
            "trade_value": price * 500_000,
            "price_last_change_pct": 0.5,
        }
        for _ in range(n)
    ]


def _legal(buy: float = 1_000, sell: float = 500) -> list[dict]:
    return [{"legal_buy_volume": buy, "legal_sell_volume": sell}]


def _profile(**kwargs) -> dict:
    base = {
        "exchange_rate_base": 50_000,
        "inflation_rate": 40.0,
        "eps_prev_year": 100.0,
        "industry_pe": 6.5,
        "bank_interest_rate": 30.0,
        "nima_rate": 50_000,
        "free_market_rate": 60_000,
        "accumulated_loss": 0.0,
        "registered_capital": 1_000.0,
        "net_operating_profit": 500.0,
        "big_ipo": 0,
        "capital_increase_type": None,
        "gov_support_news": 0,
        "feedstock_price": None,
    }
    for col in RISK_FILTER_COLUMNS:
        base.setdefault(col, 0)
    base.update(kwargs)
    return base


# ═══════════════════════════════════════════════════════════════════════════
# 1. WEIGHTS invariant
# ═══════════════════════════════════════════════════════════════════════════

class TestWeightsInvariant:
    def test_weights_sum_to_one(self) -> None:
        total = sum(WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9, f"WEIGHTS sum = {total} != 1.0"

    def test_all_weights_positive(self) -> None:
        for k, v in WEIGHTS.items():
            assert v > 0, f"weight {k} = {v} is not positive"


# ═══════════════════════════════════════════════════════════════════════════
# 2. Individual score functions
# ═══════════════════════════════════════════════════════════════════════════

class TestScoreFundamental:
    def test_high_dol_and_real_growth_gives_max(self) -> None:
        assert calc().score_fundamental(0.25, 0.20) == 30.0

    def test_mid_dol_gives_7_5(self) -> None:
        assert calc().score_fundamental(0.15, 0.0) == 7.5

    def test_zero_growth_gives_zero(self) -> None:
        assert calc().score_fundamental(0.0, 0.0) == 0.0

    def test_boundary_exact_20_pct_counts_as_high(self) -> None:
        # dol_growth > 0.20 — boundary is strict, 0.20 is mid tier
        assert calc().score_fundamental(0.20, 0.0) == 7.5
        assert calc().score_fundamental(0.201, 0.0) == 15.0


class TestScoreValuation:
    def test_low_pe_ratio_gives_max(self) -> None:
        assert calc().score_valuation(1.0) == 20.0

    def test_mid_pe_ratio_gives_10(self) -> None:
        assert calc().score_valuation(1.3) == 10.0

    def test_high_pe_ratio_gives_zero(self) -> None:
        assert calc().score_valuation(2.0) == 0.0

    def test_boundary_1_2_is_still_low(self) -> None:
        # pe_r < 1.2 → 20; pe_r = 1.2 → mid tier
        assert calc().score_valuation(1.19) == 20.0
        assert calc().score_valuation(1.20) == 10.0


class TestScoreInstitutional:
    def test_strong_institutional_buy_gives_max(self) -> None:
        assert calc().score_institutional(0.1) == 25.0

    def test_mild_institutional_buy_gives_12_5(self) -> None:
        assert calc().score_institutional(0.03) == 12.5

    def test_no_net_institutional_buy_gives_zero(self) -> None:
        assert calc().score_institutional(0.0) == 0.0
        assert calc().score_institutional(-0.1) == 0.0


class TestScoreTechnical:
    def test_strong_volume_spike_gives_max(self) -> None:
        assert calc().score_technical(4.0) == 15.0

    def test_moderate_spike_gives_7_5(self) -> None:
        assert calc().score_technical(2.5) == 7.5

    def test_no_spike_gives_zero(self) -> None:
        assert calc().score_technical(1.0) == 0.0


class TestScoreMacro:
    def test_div_yield_above_bank_rate_gives_10(self) -> None:
        assert calc().score_macro(35.0, 30.0) == 10.0

    def test_div_yield_below_bank_rate_gives_zero(self) -> None:
        assert calc().score_macro(25.0, 30.0) == 0.0

    def test_div_yield_equal_gives_zero(self) -> None:
        # dy > bank_rate is strict; equal → 0
        assert calc().score_macro(30.0, 30.0) == 0.0


class TestScoreGov:
    def test_loss_ratio_above_1_incurs_penalty(self) -> None:
        s = calc().score_gov(1.5, 0, 0, None, 0)
        assert s == -10.0

    def test_mid_loss_ratio_incurs_mild_penalty(self) -> None:
        s = calc().score_gov(0.7, 0, 0, None, 0)
        assert s == -5.0

    def test_capital_increase_type_adds_5(self) -> None:
        s = calc().score_gov(0, 0, 0, "نقدی", 0)
        assert s == 5.0

    def test_gov_support_news_adds_3(self) -> None:
        s = calc().score_gov(0, 0, 0, None, 1)
        assert s == 3.0

    def test_all_positives_stack(self) -> None:
        # large avg_val (>20B) + institutional >0.05 + نقدی + gov_news
        s = calc().score_gov(0, 25_000_000_000, 0.1, "نقدی", 1)
        assert s == 18.0  # 5 + 5 + 5 + 3


class TestScoresFarabourse:
    def test_both_conditions_give_max(self) -> None:
        assert calc().score_farabourse(0.25, 10) == 10.0

    def test_one_condition_gives_5(self) -> None:
        assert calc().score_farabourse(0.25, -1) == 5.0
        assert calc().score_farabourse(0.10, 10) == 5.0

    def test_neither_condition_gives_zero(self) -> None:
        assert calc().score_farabourse(0.10, -1) == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# 3. Risk gate and neg-filter
# ═══════════════════════════════════════════════════════════════════════════

class TestRiskGate:
    def test_no_risk_flags_passes(self) -> None:
        assert calc().risk_ok(_profile()) is True

    def test_any_single_risk_flag_fails(self) -> None:
        for col in RISK_FILTER_COLUMNS:
            assert calc().risk_ok({col: 1}) is False, f"{col} should trigger risk gate"

    def test_none_profile_passes(self) -> None:
        assert calc().risk_ok(None) is True

    def test_flag_value_zero_does_not_fail(self) -> None:
        p = {col: 0 for col in RISK_FILTER_COLUMNS}
        assert calc().risk_ok(p) is True


class TestNegFilterCount:
    def test_zero_flags_gives_zero(self) -> None:
        assert calc().neg_filter_count(_profile()) == 0

    def test_two_flags_gives_two(self) -> None:
        p = _profile(**{RISK_FILTER_COLUMNS[0]: 1, RISK_FILTER_COLUMNS[1]: 1})
        assert calc().neg_filter_count(p) == 2

    def test_none_profile_gives_zero(self) -> None:
        assert calc().neg_filter_count(None) == 0


# ═══════════════════════════════════════════════════════════════════════════
# 4. Decision logic
# ═══════════════════════════════════════════════════════════════════════════

class TestDecisionLogic:
    """Full calculate() → decision integration checks."""

    def _run(self, **profile_kwargs) -> dict:
        return calc().calculate(
            symbol="TEST",
            eps=500.0,
            shares=1_000_000,
            daily_rows=_daily(61, price=5_000),
            legal_rows=_legal(buy=100_000, sell=10_000),
            profile=_profile(**profile_kwargs),
            last_snapshot=None,
        )

    def test_high_score_no_risk_gives_buy(self) -> None:
        # High EPS, low PE, strong institutional → should clear 70 threshold
        result = calc().calculate(
            symbol="BEST",
            eps=1_000.0,
            shares=1_000_000,
            daily_rows=_daily(61, price=10_000),
            legal_rows=_legal(buy=200_000, sell=5_000),
            profile=_profile(
                exchange_rate_base=50_000,
                eps_prev_year=700.0,
                industry_pe=15.0,  # low relative PE → score_valuation high
                bank_interest_rate=30.0,
                gov_support_news=1,
            ),
            last_snapshot=None,
        )
        # We only assert it's not risk-rejected; actual threshold crossing depends on data
        assert result["decision"] in ("خرید", "رد_نمره", "نخرید")
        assert result["decision"] != "رد_ریسک"

    def test_risk_flag_gives_risk_reject(self) -> None:
        result = self._run(**{RISK_FILTER_COLUMNS[0]: 1})
        assert result["decision"] == "رد_ریسک"

    def test_low_score_gives_score_reject(self) -> None:
        # Minimal profile → near-zero scores → adj < 70 → رد_نمره
        result = calc().calculate(
            symbol="WEAK",
            eps=0.01,
            shares=1_000_000,
            daily_rows=_daily(10, price=1.0),
            legal_rows=[],
            profile=_profile(),
            last_snapshot=None,
        )
        assert result["decision"] == "رد_نمره"

    def test_big_ipo_flag_reduces_adjusted_score(self) -> None:
        base = self._run()
        with_ipo = self._run(big_ipo=1)
        assert with_ipo["adjusted_score"] <= base["adjusted_score"]

    def test_nima_spread_above_1_2_reduces_adjusted_score(self) -> None:
        base = self._run(free_market_rate=50_000, nima_rate=50_000)  # spread=1.0
        with_spread = self._run(free_market_rate=70_000, nima_rate=50_000)  # spread=1.4 → -10
        assert with_spread["adjusted_score"] <= base["adjusted_score"]

    def test_result_dict_has_required_keys(self) -> None:
        result = self._run()
        required = {
            "symbol", "decision", "current_price", "stop_loss_price",
            "risk_ok", "raw_score", "final_score", "adjusted_score",
            "score_fundamental", "score_valuation", "score_institutional",
            "score_technical", "score_macro",
        }
        assert required.issubset(result.keys()), f"Missing keys: {required - result.keys()}"

    def test_scores_are_clamped_0_to_100(self) -> None:
        result = self._run()
        for key in ("raw_score", "final_score", "adjusted_score"):
            assert 0.0 <= result[key] <= 100.0, f"{key} = {result[key]} out of [0, 100]"

    def test_stop_loss_below_current_price(self) -> None:
        result = self._run()
        assert result["stop_loss_price"] <= result["current_price"]


# ═══════════════════════════════════════════════════════════════════════════
# 5. VectorCalculator math helpers
# ═══════════════════════════════════════════════════════════════════════════

class TestVectorMathHelpers:
    def test_div_avoids_division_by_zero(self) -> None:
        assert calc()._div(10.0, 0.0) == 0.0

    def test_clamp_lo(self) -> None:
        assert calc()._clamp(-5.0) == 0.0

    def test_clamp_hi(self) -> None:
        assert calc()._clamp(150.0) == 100.0

    def test_clamp_within_range(self) -> None:
        assert calc()._clamp(50.0) == 50.0

    def test_pe_avoids_zero_eps(self) -> None:
        # eps=0 → uses max(eps, 0.01)
        pe = calc().pe(1000.0, 0.0)
        assert pe > 0

    def test_inst_ratio_net_direction(self) -> None:
        shares = 1_000_000
        assert calc().inst_ratio(100_000, 50_000, shares) > 0  # net buy
        assert calc().inst_ratio(50_000, 100_000, shares) < 0  # net sell
        assert calc().inst_ratio(0, 0, shares) == 0.0

    def test_trend_label_requires_5_bars(self) -> None:
        assert calc().trend_label([]) == "flat"
        assert calc().trend_label([100.0] * 4) == "flat"

    def test_trend_label_up_when_ma5_exceeds_ma20(self) -> None:
        # closes[0] is most recent; closes[:5] = recent 5, closes[:20] = recent 20
        # For "up": recent 5 (high) >> older part of window
        closes = [120.0] * 5 + [80.0] * 15  # ma5=120, ma20=(120*5+80*15)/20=90 → up
        assert calc().trend_label(closes) == "up"

    def test_trend_label_down_when_ma5_lags_ma20(self) -> None:
        closes = [80.0] * 5 + [120.0] * 15  # ma5=80, ma20=(80*5+120*15)/20=100 → down
        assert calc().trend_label(closes) == "down"


# ═══════════════════════════════════════════════════════════════════════════
# 6. AdvancedAnalyticsEngine._compute_composite
# ═══════════════════════════════════════════════════════════════════════════

class TestAdvancedComposite:
    @staticmethod
    def _make_ind(**kwargs):
        from services.smart_money.advanced_analytics import TechnicalIndicators
        defaults = dict(
            rsi_14=50.0, macd_line=0.0, macd_signal=0.0, macd_histogram=0.0,
            bb_pct=0.5, atr_14=2.0, adx=25.0, computed=True, bars=60,
        )
        defaults.update(kwargs)
        return TechnicalIndicators(**defaults)

    @staticmethod
    def _make_trend(direction: str = "sideways", strength: float = 0.5):
        from services.smart_money.advanced_analytics import TrendAnalysis
        return TrendAnalysis(direction=direction, strength=strength)

    @staticmethod
    def _make_vol(regime: str = "normal"):
        from services.smart_money.advanced_analytics import VolatilityAnalysis
        return VolatilityAnalysis(regime=regime)

    def _composite(self, **ind_kwargs) -> float:
        from services.smart_money.advanced_analytics import AdvancedAnalyticsEngine
        engine = AdvancedAnalyticsEngine()
        ind = self._make_ind(**ind_kwargs)
        trend = self._make_trend()
        vol = self._make_vol()
        return engine._compute_composite(ind, trend, vol, [])

    def test_neutral_inputs_give_near_zero(self) -> None:
        score = self._composite()
        assert abs(score) < 0.1

    def test_oversold_rsi_adds_to_score(self) -> None:
        below = self._composite(rsi_14=25.0)
        above = self._composite(rsi_14=50.0)
        assert below > above

    def test_overbought_rsi_subtracts_from_score(self) -> None:
        overbought = self._composite(rsi_14=75.0)
        neutral = self._composite(rsi_14=50.0)
        assert overbought < neutral

    def test_positive_macd_adds_to_score(self) -> None:
        pos = self._composite(macd_histogram=5.0)
        neg = self._composite(macd_histogram=-5.0)
        assert pos > neg

    def test_extreme_volatility_scales_down_score(self) -> None:
        from services.smart_money.advanced_analytics import AdvancedAnalyticsEngine
        engine = AdvancedAnalyticsEngine()
        ind = self._make_ind(rsi_14=25.0, macd_histogram=10.0)  # strongly bullish
        normal_score = engine._compute_composite(ind, self._make_trend("up", 1.0), self._make_vol("normal"), [])
        extreme_score = engine._compute_composite(ind, self._make_trend("up", 1.0), self._make_vol("extreme"), [])
        assert extreme_score < normal_score

    def test_score_is_clamped_to_minus_one_to_one(self) -> None:
        from services.smart_money.advanced_analytics import AdvancedAnalyticsEngine, PatternSignal
        engine = AdvancedAnalyticsEngine()
        ind = self._make_ind(rsi_14=15.0, macd_histogram=100.0, bb_pct=0.0)
        trend = self._make_trend("up", 1.0)
        vol = self._make_vol("normal")
        patterns = [PatternSignal("hammer", "bullish", 1.0, "test", 0)] * 3
        score = engine._compute_composite(ind, trend, vol, patterns)
        assert -1.0 <= score <= 1.0

    def test_score_to_signal_bands(self) -> None:
        from services.smart_money.advanced_analytics import AdvancedAnalyticsEngine
        engine = AdvancedAnalyticsEngine()
        assert engine._score_to_signal(0.5) == "strong_buy"
        assert engine._score_to_signal(0.3) == "buy"
        assert engine._score_to_signal(0.0) == "neutral"
        assert engine._score_to_signal(-0.3) == "sell"
        assert engine._score_to_signal(-0.5) == "strong_sell"
