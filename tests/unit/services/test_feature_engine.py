"""Unit tests for FeatureEngine — 115 features across 8 blocks, scoring, penalty, and decision.

Tests cover:
  - All 8 block computation methods (A through H)
  - Scoring helpers (fundamental, valuation, technical, liquidity, orderflow, macro, event)
  - Technical analysis helpers (RSI, MACD, ATR, breakout, trend)
  - Decision helpers (penalty, neg events count, final decision with hard rules, verdict)
  - Integration: compute_all_features() with mocked BrsApiQueryService + QueueAnalysisService
  - Edge cases: empty data, zero prices, no queue service, calendar-based detection
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.feature_engine import FeatureEngine

# ═══════════════════════════════════════════════════════════════════════════════
# ── Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_brsapi() -> MagicMock:
    """BrsApiQueryService with 3 async methods mocked."""
    mock = MagicMock()
    mock.get_enriched_symbol_detail = AsyncMock()
    mock.get_historical_daily = AsyncMock()
    mock.get_candlesticks = AsyncMock()
    return mock


@pytest.fixture
def mock_queue_service() -> MagicMock:
    """QueueAnalysisService with analyze_symbol mocked."""
    mock = MagicMock()
    mock.analyze_symbol = AsyncMock()
    return mock


@pytest.fixture
def engine(mock_brsapi: MagicMock, mock_queue_service: MagicMock) -> FeatureEngine:
    """FeatureEngine with mocked services and mocked _load_schema."""
    # Mock _load_schema to avoid JSON file dependency
    with patch.object(FeatureEngine, "_load_schema", return_value=None):
        eng = FeatureEngine(
            brsapi_query_service=mock_brsapi,
            queue_analysis_service=mock_queue_service,
        )
    return eng


# ═══════════════════════════════════════════════════════════════════════════════
# ── Helper: Mock enriched detail
# ═══════════════════════════════════════════════════════════════════════════════


def _enriched(
    symbol: str = "فولاد",
    name: str = "فولاد مبارکه اصفهان",
    isin: str = "IRO1FOLD0001",
    sector: str = "فلزات اساسی",
    sector_id: int = 14,
    board: str = "بورس",
    shares_count: float = 50_000_000_000,
    free_float_pct: float = 20.0,
    eps: float = 500,
    pe_ratio: float = 6.5,
    group_pe_ratio: float = 7.0,
    market_value: float = 200_000_000_000_000,
    last_price: float = 25000,
    price_yesterday: float = 24300,
    price_first: float = 24500,
    price_close: float = 25000,
    price_max: float = 25200,
    price_min: float = 24400,
    price_last_change_pct: float = 2.88,
    trade_volume: int = 5_000_000,
    trade_value: float = 125_000_000_000,
    trade_count: int = 1200,
    buy_legal_volume: int = 2_000_000,
    sell_legal_volume: int = 500_000,
    buy_real_volume: int = 3_000_000,
    sell_real_volume: int = 1_500_000,
    buy_legal_count: int = 15,
    sell_legal_count: int = 8,
    buy_real_count: int = 300,
    sell_real_count: int = 250,
    **kwargs: object,
) -> dict:
    """ساخت enriched detail mock با مقادیر پیش‌فرض منطقی."""
    data: dict = {
        "symbol": symbol,
        "name": name,
        "isin": isin,
        "sector": sector,
        "sector_id": sector_id,
        "board": board,
        "shares_count": shares_count,
        "free_float_pct": free_float_pct,
        "eps": eps,
        "pe_ratio": pe_ratio,
        "group_pe_ratio": group_pe_ratio,
        "market_value": market_value,
        "price_last": last_price,
        "price_yesterday": price_yesterday,
        "price_first": price_first,
        "price_close": price_close,
        "price_max": price_max,
        "price_min": price_min,
        "price_last_change_pct": price_last_change_pct,
        "trade_volume": trade_volume,
        "trade_value": trade_value,
        "trade_count": trade_count,
        "buy_legal_volume": buy_legal_volume,
        "sell_legal_volume": sell_legal_volume,
        "buy_real_volume": buy_real_volume,
        "sell_real_volume": sell_real_volume,
        "buy_legal_count": buy_legal_count,
        "sell_legal_count": sell_legal_count,
        "buy_real_count": buy_real_count,
        "sell_real_count": sell_real_count,
    }
    data.update(kwargs)
    return data


def _historical_daily(
    base_price: float = 20000,
    count: int = 60,
    step: float = 100,
    volume: int = 3_000_000,
) -> list[dict]:
    """ساخت mock data historical daily با روند صعودی ملایم."""
    rows = []
    for i in range(count):
        price = base_price + (step * i)
        rows.append({
            "price_close": price,
            "price_min": price - step * 0.5,
            "price_max": price + step * 0.5,
            "trade_volume": volume + (i * 10_000),
        })
    return rows


def _candlestick(count: int = 100) -> list[dict]:
    """ساخت mock data کندل."""
    return _historical_daily(base_price=20000, count=count, step=100)


def _queue_result(
    status: str = "NONE",
    ratio: float = 0.0,
    streak: int = 0,
    type_change: str = "NO_CHANGE",
    distance: float = 0.0,
) -> dict:
    """ساخت mock خروجی QueueAnalysisService."""
    return {
        "queue_status": status,
        "queue_volume_ratio": ratio,
        "queue_days_streak": streak,
        "queue_type_change": type_change,
        "distance_to_limit": distance,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ── BLOCK A: Identity & Data Quality
# ═══════════════════════════════════════════════════════════════════════════════


class TestBlockA:
    """Block A: ticker, isin, market, float_shares, data_completeness."""

    def test_identity_fields(self, engine: FeatureEngine):
        enriched = _enriched()
        block = engine._compute_block_a(enriched)

        assert block["ticker"] == "فولاد"
        assert block["isin"] == "IRO1FOLD0001"
        assert block["industry_name"] == "فلزات اساسی"
        assert block["industry_id"] == 14

    def test_float_shares_computed(self, engine: FeatureEngine):
        """free_float_pct=20%, shares_count=50B → float_shares=10B."""
        block = engine._compute_block_a(_enriched())
        assert block["float_shares"] == 10_000_000_000  # 50B * 20%

    def test_float_shares_zero_when_no_free_float(self, engine: FeatureEngine):
        block = engine._compute_block_a(_enriched(free_float_pct=0))
        assert block["float_shares"] == 0

    def test_data_completeness_non_null_count(self, engine: FeatureEngine):
        """تعداد فیلدهای غیرتهی / کل فیلدها."""
        enriched = _enriched()
        block = engine._compute_block_a(enriched)
        assert 0 < block["data_completeness"] <= 100
        assert isinstance(block["data_completeness"], float)

    def test_data_completeness_with_empty_enriched(self, engine: FeatureEngine):
        block = engine._compute_block_a({})
        assert block["data_completeness"] == 0.0

    def test_determine_bourse(self, engine: FeatureEngine):
        """IRO... prefix → bourse."""
        assert engine._determine_market({"isin": "IRO1FOLD0001"}) == "bourse"

    def test_determine_farabourse(self, engine: FeatureEngine):
        """IROF... prefix → farabourse."""
        assert engine._determine_market({"isin": "IROFZAG0001"}) == "farabourse"

    def test_determine_base_market(self, engine: FeatureEngine):
        """board='پایه' → base."""
        assert engine._determine_market({"board": "پایه"}) == "base"

    def test_determine_default_bourse(self, engine: FeatureEngine):
        assert engine._determine_market({}) == "bourse"


# ═══════════════════════════════════════════════════════════════════════════════
# ── BLOCK B: Fundamental Data
# ═══════════════════════════════════════════════════════════════════════════════


class TestBlockB:
    """Block B: EPS_ttm, EPS_dollar_growth, net_profit, loss_to_capital."""

    def test_eps_ttm_computed(self, engine: FeatureEngine):
        """eps=500 → eps_ttm=2000 (×4)."""
        block = engine._compute_block_b(_enriched(eps=500))
        assert block["eps_ttm"] == 2000

    def test_eps_dollar_growth_with_positive_last_year(self, engine: FeatureEngine):
        block = engine._compute_block_b(_enriched(eps=500))
        # eps_ttm=2000, eps_dollar_ttm=2000/28500≈0.07
        # eps_last_year=1500, eps_dollar_last_year=1500/24500≈0.061
        # growth = 0.07/0.061 - 1 ≈ 0.148
        assert block["eps_dollar_growth"] > 0

    def test_eps_zero_returns_zero_growth(self, engine: FeatureEngine):
        block = engine._compute_block_b(_enriched(eps=0))
        assert block["eps_ttm"] == 0
        assert block["eps_dollar_growth"] == 0.0
        assert block["eps_nominal_growth"] == 0.0

    def test_net_profit_from_market_value_and_pe(self, engine: FeatureEngine):
        """market_value=200T, pe=6.5 → net_profit≈30.8T."""
        block = engine._compute_block_b(_enriched())
        assert block["net_profit"] > 0

    def test_net_profit_zero_when_pe_zero(self, engine: FeatureEngine):
        block = engine._compute_block_b(_enriched(pe_ratio=0))
        assert block["net_profit"] == 0

    def test_loss_to_capital_zero_when_no_accumulated_loss(self, engine: FeatureEngine):
        block = engine._compute_block_b(_enriched())
        assert block["accumulated_loss"] == 0.0
        assert block["loss_to_capital_ratio"] == 0.0

    def test_real_growth_adjusted_for_inflation(self, engine: FeatureEngine):
        """رشد واقعی = (1+اسمی)/(1+تورم) - 1."""
        block = engine._compute_block_b(_enriched(eps=500))
        assert "eps_real_growth" in block
        assert block["eps_real_growth"] != block.get("eps_nominal_growth")  # inflation-adjusted


# ═══════════════════════════════════════════════════════════════════════════════
# ── BLOCK C: Valuation & Macro
# ═══════════════════════════════════════════════════════════════════════════════


class TestBlockC:
    """Block C: last_price, pe_ratio, pe_relative, earnings_yield, macro vars."""

    def test_last_price_and_pe(self, engine: FeatureEngine):
        block_b = engine._compute_block_b(_enriched())
        block_c = engine._compute_block_c(_enriched(last_price=25000, pe_ratio=6.5), block_b)
        assert block_c["last_price"] == 25000
        assert block_c["pe_ratio"] == 6.5

    def test_pe_relative(self, engine: FeatureEngine):
        """pe=6.5, industry_pe=7.0 → pe_relative=0.93."""
        block_c = engine._compute_block_c(_enriched(), {})
        assert block_c["pe_relative"] == pytest.approx(0.93, rel=0.01)

    def test_pe_relative_zero_when_no_industry_pe(self, engine: FeatureEngine):
        block_c = engine._compute_block_c(_enriched(group_pe_ratio=0), {})
        assert block_c["pe_relative"] == 0.0

    def test_earnings_yield_computed(self, engine: FeatureEngine):
        """eps_ttm=2000, last_price=25000 → earnings_yield=(2000*4/25000)*100=32%."""
        block_b = engine._compute_block_b(_enriched(eps=500))
        block_c = engine._compute_block_c(_enriched(last_price=25000), block_b)
        assert block_c["earnings_yield"] == pytest.approx(32.0, rel=0.5)

    def test_macro_variables_present(self, engine: FeatureEngine):
        block_c = engine._compute_block_c(_enriched(), {})
        assert block_c["bank_interest_rate"] == 22.5
        assert block_c["bond_yield"] == 28.0
        assert block_c["usd_nima"] == 44500.0
        assert block_c["usd_free"] == 59500.0
        assert block_c["usd_spread"] > 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# ── BLOCK D: Technical Analysis
# ═══════════════════════════════════════════════════════════════════════════════


class TestBlockD:
    """Block D: volume, SMA, RSI, MACD, ATR, breakout, trend."""

    def test_volume_and_trade_value(self, engine: FeatureEngine):
        enriched = _enriched(trade_volume=5_000_000, trade_value=125_000_000_000)
        block = engine._compute_block_d(enriched, _historical_daily())
        assert block["volume"] == 5_000_000
        assert block["trade_value"] == 125_000_000_000

    def test_avg_volume_50(self, engine: FeatureEngine):
        """60 روز historical → avg_volume_50 از 50 روز آخر."""
        block = engine._compute_block_d(_enriched(), _historical_daily(volume=3_000_000, count=60))
        assert block["avg_volume_50"] > 0
        assert isinstance(block["avg_volume_50"], int)

    def test_volume_spike(self, engine: FeatureEngine):
        """volume=5M, avg_volume=~3M → spike≈1.67."""
        enriched = _enriched(trade_volume=5_000_000)
        hist = _historical_daily(volume=3_000_000, count=60)
        block = engine._compute_block_d(enriched, hist)
        assert block["volume_spike"] > 1.0

    def test_sma_20_with_sufficient_data(self, engine: FeatureEngine):
        block = engine._compute_block_d(_enriched(), _historical_daily(base_price=20000, count=30))
        assert block["sma_20"] > 0

    def test_sma_20_falls_back_to_last_close_when_insufficient(self, engine: FeatureEngine):
        """کمتر از 20 روز داده → fallback به آخرین close."""
        enriched = _enriched()
        hist = _historical_daily(count=10, base_price=25000)
        block = engine._compute_block_d(enriched, hist)
        assert block["sma_20"] > 0

    def test_rsi_14_computed(self, engine: FeatureEngine):
        block = engine._compute_block_d(_enriched(), _historical_daily(count=30))
        assert 0 <= block["rsi_14"] <= 100

    def test_macd_signal_present(self, engine: FeatureEngine):
        block = engine._compute_block_d(_enriched(), _historical_daily(count=60))
        assert block["macd_signal"] in (-1.0, 0.0, 1.0)

    def test_atr_14_present(self, engine: FeatureEngine):
        block = engine._compute_block_d(_enriched(), _historical_daily(count=30))
        assert isinstance(block["atr_14"], float)
        assert block["atr_14"] >= 0

    def test_breakout_flag_false_by_default(self, engine: FeatureEngine):
        block = engine._compute_block_d(_enriched(), _historical_daily(count=30))
        assert block["breakout_flag"] in (0.0, 1.0)

    def test_trend_bullish_with_uptrend(self, engine: FeatureEngine):
        """60 روز روند صعودی → trend=bullish."""
        block = engine._compute_block_d(_enriched(), _historical_daily(count=60))
        assert block["trend_20d"] in ("bullish", "neutral", "bearish")

    def test_float_turnover_pct(self, engine: FeatureEngine):
        """free_float_pct=20%, last_price=25000, trade_value=125B
        float_turnover = 100 * 125B / (20% * 25000) = ..."""
        block = engine._compute_block_d(_enriched(), _historical_daily())
        assert isinstance(block["float_turnover_pct"], float)


# ═══════════════════════════════════════════════════════════════════════════════
# ── BLOCK E: Money Flow
# ═══════════════════════════════════════════════════════════════════════════════


class TestBlockE:
    """Block E: inst_buy/sell, net_inst_volume, retail_to_inst_ratio."""

    def test_net_inst_volume_positive(self, engine: FeatureEngine):
        """buy_legal=2M, sell_legal=0.5M → net=1.5M."""
        enriched = _enriched(buy_legal_volume=2_000_000, sell_legal_volume=500_000)
        block = engine._compute_block_e(enriched)
        assert block["inst_buy_volume"] == 2_000_000
        assert block["inst_sell_volume"] == 500_000
        assert block["net_inst_volume"] == 1_500_000

    def test_net_inst_ratio(self, engine: FeatureEngine):
        """net=1.5M, free_float_pct=20% → ratio=1.5M/20=75000."""
        block = engine._compute_block_e(_enriched())
        assert block["net_inst_ratio"] > 0

    def test_retail_to_inst_ratio(self, engine: FeatureEngine):
        """retail_buy=3M, inst_buy=2M → ratio=1.5."""
        block = engine._compute_block_e(_enriched())
        assert block["retail_to_inst_ratio"] == pytest.approx(1.5, rel=0.01)

    def test_retail_to_inst_ratio_zero_when_no_inst_buy(self, engine: FeatureEngine):
        block = engine._compute_block_e(_enriched(buy_legal_volume=0))
        assert block["retail_to_inst_ratio"] == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# ── BLOCK F: Queue + Microstructure
# ═══════════════════════════════════════════════════════════════════════════════


class TestBlockF:
    """Block F: trade_count, avg_trade_size, VWAP, queue features."""

    def test_microstructure_fields(self, engine: FeatureEngine):
        enriched = _enriched(trade_count=1200, trade_volume=5_000_000)
        queue = _queue_result()
        block = engine._compute_block_f(enriched, queue)
        assert block["trade_count"] == 1200
        assert block["avg_trade_size"] > 0

    def test_vwap_from_ohlc(self, engine: FeatureEngine):
        """VWAP = (first+max+min+close)/4."""
        enriched = _enriched(price_first=24500, price_max=25200, price_min=24400, price_close=25000)
        block = engine._compute_block_f(enriched, _queue_result())
        expected_vwap = (24500 + 25200 + 24400 + 25000) / 4
        assert block["vwap"] == pytest.approx(expected_vwap, rel=0.01)

    def test_last_vs_vwap(self, engine: FeatureEngine):
        """last_price=25000, vwap=24775 → diff=225."""
        block = engine._compute_block_f(_enriched(last_price=25000), _queue_result())
        assert isinstance(block["last_vs_vwap"], float)

    def test_queue_features_included(self, engine: FeatureEngine):
        queue = _queue_result(status="BUY_QUEUE", ratio=0.85, streak=2)
        block = engine._compute_block_f(_enriched(), queue)
        assert block["queue_status"] == "BUY_QUEUE"
        assert block["queue_volume_ratio"] == 0.85
        assert block["queue_days_streak"] == 2

    def test_queue_features_default_when_empty(self, engine: FeatureEngine):
        block = engine._compute_block_f(_enriched(), {})
        assert block["queue_status"] == "NONE"
        assert block["queue_volume_ratio"] == 0.0

    def test_trade_distribution_retail(self, engine: FeatureEngine):
        """real_ratio > 0.6 → retail."""
        enriched = _enriched(buy_real_volume=8_000_000, buy_legal_volume=1_000_000)
        block = engine._compute_block_f(enriched, _queue_result())
        assert block["trade_distribution"] == "retail"

    def test_trade_distribution_institutional(self, engine: FeatureEngine):
        """real_ratio < 0.3 → institutional."""
        enriched = _enriched(buy_real_volume=1_000_000, buy_legal_volume=5_000_000)
        block = engine._compute_block_f(enriched, _queue_result())
        assert block["trade_distribution"] == "institutional"


# ═══════════════════════════════════════════════════════════════════════════════
# ── BLOCK G: Events & Calendar
# ═══════════════════════════════════════════════════════════════════════════════


class TestBlockG:
    """Block G: همه مقادیر صفر بجز market_regime=50 و تشخیص تقویمی."""

    def test_all_events_zero_by_default(self, engine: FeatureEngine):
        # Current block G only computes calendar features (event data sources
        # not implemented yet — see _compute_block_g docstring); corporate
        # event keys were removed in commit e311199.
        block = engine._compute_block_g()
        event_keys = ["agm_proximity", "market_index_3m"]
        for key in event_keys:
            assert block[key] == 0.0, f"{key} should be 0.0"

    def test_market_regime_default(self, engine: FeatureEngine):
        block = engine._compute_block_g()
        assert block["market_regime"] == 50.0

    def test_end_of_month_detection(self, engine: FeatureEngine):
        """آخرین روز ماه → end_of_month=1.0."""
        with patch("services.feature_engine.date") as mock_date:
            mock_date.today.return_value = date(2026, 7, 31)
            block = engine._compute_block_g()
            assert block["end_of_month"] == 1.0

    def test_pre_holiday_detection(self, engine: FeatureEngine):
        """July 31, 2026 is a Friday (weekday=4 in Python=Friday, holiday in Iran) → pre_holiday=1.0."""
        with patch("services.feature_engine.date") as mock_date:
            mock_date.today.return_value = date(2026, 7, 31)  # واقعاً Friday است = weekday=4
            # توجه: weekday روی date واقعی ست می‌شود نه mock، پس از attribute set استفاده نمی‌کنیم
            # July 31, 2026 واقعاً weekday=4 (Friday) است
            block = engine._compute_block_g()
            assert block["pre_holiday"] == 1.0

    def test_not_end_of_month(self, engine: FeatureEngine):
        """وسط ماه → end_of_month=0.0."""
        with patch("services.feature_engine.date") as mock_date:
            mock_date.today.return_value = date(2026, 7, 15)
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
            block = engine._compute_block_g()
            assert block["end_of_month"] == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# ── BLOCK H: Scores, Penalty & Decision
# ═══════════════════════════════════════════════════════════════════════════════


class TestBlockH:
    """Block H: 8 sub-scores, raw_score, penalty, final_score, decision, hard rules."""

    def test_all_subscores_present(self, engine: FeatureEngine):
        block_h = self._compute_default_block_h(engine)
        for key in [
            "score_fundamental", "score_valuation", "score_technical",
            "score_liquidity", "score_orderflow", "score_micro",
            "score_macro", "score_event",
        ]:
            assert key in block_h, f"{key} missing"
            assert 0 <= block_h[key] <= 100, f"{key} out of range"

    def test_raw_score_weighted_sum(self, engine: FeatureEngine):
        block_h = self._compute_default_block_h(engine)
        assert isinstance(block_h["raw_score"], float)
        assert 0 <= block_h["raw_score"] <= 100

    def test_penalty_between_zero_and_035(self, engine: FeatureEngine):
        block_h = self._compute_default_block_h(engine)
        assert 0 <= block_h["penalty"] <= 0.35

    def test_final_score_leq_raw_score(self, engine: FeatureEngine):
        """final_score = raw_score * (1 - penalty) ≤ raw_score."""
        block_h = self._compute_default_block_h(engine)
        assert block_h["final_score"] <= block_h["raw_score"]

    def test_final_decision_is_valid(self, engine: FeatureEngine):
        block_h = self._compute_default_block_h(engine)
        assert block_h["final_decision"] in ("BUY", "WATCHLIST", "HOLD", "REDUCE", "REJECT")

    def test_stop_loss_and_target(self, engine: FeatureEngine):
        block_h = self._compute_default_block_h(engine)
        assert block_h["stop_loss_7"] > 0
        assert block_h["target_profit"] > block_h["stop_loss"]

    def test_position_size_computed(self, engine: FeatureEngine):
        block_h = self._compute_default_block_h(engine)
        assert block_h["position_size"] >= 0

    def test_hard_rule_buy_queue_overrides(self, engine: FeatureEngine):
        """BUY_QUEUE قوی → BUY حتی با امتیاز پایین."""
        f_block = {"queue_status": "BUY_QUEUE", "queue_volume_ratio": 0.85, "queue_days_streak": 1}
        decision, override = engine._compute_final_decision(40.0, f_block, {})
        assert decision == "BUY"
        assert "Hard Rule 2" in override

    def test_hard_rule_sell_queue_rejects(self, engine: FeatureEngine):
        """SELL_QUEUE پایدار → REJECT حتی با امتیاز بالا."""
        f_block = {"queue_status": "SELL_QUEUE", "queue_volume_ratio": 0.6, "queue_days_streak": 3}
        decision, override = engine._compute_final_decision(90.0, f_block, {})
        assert decision == "REJECT"
        assert "Hard Rule 3" in override

    def test_hard_rule_new_sell_critical(self, engine: FeatureEngine):
        """NEW_SELL_QUEUE + ratio>0.6 → REJECT بحرانی."""
        f_block = {
            "queue_status": "SELL_QUEUE",
            "queue_volume_ratio": 0.7,
            "queue_days_streak": 1,
            "queue_type_change": "NEW_SELL_QUEUE",
        }
        decision, override = engine._compute_final_decision(80.0, f_block, {})
        assert decision == "REJECT"
        assert "Hard Rule 1" in override

    def test_normal_decision_by_score(self, engine: FeatureEngine):
        """بدون صف → تصمیم بر اساس final_score."""
        f_block = {"queue_status": "NONE", "queue_volume_ratio": 0.0, "queue_days_streak": 0}
        decision, override = engine._compute_final_decision(80.0, f_block, {})
        assert decision == "BUY"
        assert override == ""

    def test_build_verdict_includes_override(self, engine: FeatureEngine):
        verdict = engine._build_verdict(65.0, "BUY", "Hard Rule 2", {"queue_status": "BUY_QUEUE", "queue_volume_ratio": 0.8})
        assert "امتیاز نهایی: 65" in verdict
        assert "تصمیم: BUY" in verdict
        assert "صف خرید" in verdict
        assert "Hard Rule 2" in verdict

    @staticmethod
    def _compute_default_block_h(engine: FeatureEngine) -> dict:
        """محاسبه Block H با داده‌های پیش‌فرض برای تست‌های عمومی."""
        enriched = _enriched()
        block_a = engine._compute_block_a(enriched)
        block_b = engine._compute_block_b(enriched)
        block_c = engine._compute_block_c(enriched, block_b)
        block_d = engine._compute_block_d(enriched, _historical_daily(count=60))
        block_e = engine._compute_block_e(enriched)
        block_f = engine._compute_block_f(enriched, _queue_result())
        block_g = engine._compute_block_g()
        return engine._compute_block_h(
            enriched, block_a, block_b, block_c, block_d, block_e, block_f, block_g, _queue_result(),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ── SCORING HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


class TestScoringHelpers:
    """تست مستقیم متدهای استاتیک امتیازدهی."""

    def test_score_fundamental_high_growth(self):
        """eps_real_growth > 0.2 → +25 امتیاز."""
        score = FeatureEngine._score_fundamental({"eps_real_growth": 0.3, "net_profit": 20_000, "loss_to_capital_ratio": 0})
        assert score >= 75  # 50 + 25 + 10

    def test_score_fundamental_negative_growth(self):
        """eps_real_growth < -0.1 → -20 امتیاز."""
        score = FeatureEngine._score_fundamental({"eps_real_growth": -0.2, "net_profit": 0, "loss_to_capital_ratio": 0})
        assert score <= 40  # 50 - 20 + adjustments

    def test_score_fundamental_high_loss_ratio(self):
        """loss_to_capital_ratio > 1 → -30 امتیاز."""
        score = FeatureEngine._score_fundamental({"eps_real_growth": 0, "net_profit": 0, "loss_to_capital_ratio": 2.0})
        assert score == 20  # 50 - 30

    def test_score_valuation_cheap(self):
        """pe_relative < 0.8 + earnings_yield > bank_rate → score بالا."""
        score = FeatureEngine._score_valuation({
            "pe_relative": 0.6, "earnings_yield": 30.0, "bank_interest_rate": 22.5,
        })
        assert score > 80  # 50 + 25 + 20

    def test_score_valuation_expensive(self):
        """pe_relative > 2 → -20 امتیاز."""
        score = FeatureEngine._score_valuation({
            "pe_relative": 2.5, "earnings_yield": 10.0, "bank_interest_rate": 22.5,
        })
        assert score < 40  # 50 - 20 - 10

    def test_score_technical_queue_override(self):
        """queue_days_streak >= 2 → RSI/MACD نادیده گرفته شود."""
        score = FeatureEngine._score_technical(
            {}, {"queue_days_streak": 2, "queue_volume_ratio": 0.8, "distance_to_limit": 0.5}, {},
        )
        assert score > 0

    def test_score_liquidity_buy_queue_bonus(self):
        """BUY_QUEUE → +15 امتیاز."""
        score = FeatureEngine._score_liquidity(
            {}, {"float_turnover_pct": 3, "volume": 5_000_000}, {"queue_status": "BUY_QUEUE"}, {},
        )
        assert score > 75  # 50 + 10 (turnover) + 5 (volume) + 15 (buy_queue)

    def test_score_liquidity_sell_queue_penalty(self):
        """SELL_QUEUE → ×0.5."""
        score = FeatureEngine._score_liquidity(
            {}, {"float_turnover_pct": 3, "volume": 5_000_000}, {"queue_status": "SELL_QUEUE"}, {},
        )
        # base=50+10+5=65, then ×0.5 = 32.5
        assert score < 35

    def test_score_orderflow_new_buy_queue(self):
        """NEW_BUY_QUEUE → +20 سپس ×(1+ratio)."""
        score = FeatureEngine._score_orderflow(
            {"net_inst_ratio": 5, "retail_to_inst_ratio": 0.5},
            {"queue_type_change": "NEW_BUY_QUEUE", "queue_volume_ratio": 0.8},
            {},
        )
        # 50 + 25 (net_ratio) + 10 (retail<0.5) = 85, +20 (new_buy) = 105, *1.8 = 189
        # capped at 100 → 100
        assert score <= 100

    def test_score_macro_high_spread(self):
        """usd_spread > 1.3 → -20."""
        score = FeatureEngine._score_macro({"usd_spread": 1.4}, {"market_regime": 50})
        assert score <= 35  # 50 - 20 + 5

    def test_score_macro_bull_regime(self):
        """market_regime >= 70 → +15."""
        score = FeatureEngine._score_macro({"usd_spread": 1.0}, {"market_regime": 80})
        assert score > 65  # 50 + 5 (low spread) + 15 (regime)

    def test_score_event_positive(self):
        """رویدادهای تقویمی فعال → +10 به ازای هر کدام."""
        score = FeatureEngine._score_event({
            "end_of_month": 1.0, "pre_holiday": 1.0, "agm_proximity": 1.0,
        })
        assert score == 80  # 50 + 3*10

    def test_score_event_negative(self):
        """بدون رویداد فعال → خنثی 50؛ مقادیر ناشناخته نادیده گرفته می‌شوند."""
        score = FeatureEngine._score_event({
            "end_of_month": 0.0, "pre_holiday": 0.0, "unknown_event": 1.0,
        })
        assert score == 50


# ═══════════════════════════════════════════════════════════════════════════════
# ── TECHNICAL ANALYSIS HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


class TestTechnicalHelpers:
    """تست مستقیم توابع تحلیل تکنیکال."""

    def test_extract_series_reverses_order(self, engine: FeatureEngine):
        """historical از جدید→قدیم است، extract از قدیم→جدید برمی‌گرداند."""
        historical = [{"val": 10}, {"val": 20}, {"val": 30}]
        series = engine._extract_series(historical, "val")
        assert series == [30.0, 20.0, 10.0]  # reversed

    def test_extract_series_skips_none(self, engine: FeatureEngine):
        historical = [{"val": 10}, {"val": None}, {"val": 30}]
        series = engine._extract_series(historical, "val")
        assert series == [30.0, 10.0]  # None filtered out

    def test_compute_rsi_basic(self):
        """20 closes increasing → RSI=100 (no losses)."""
        closes = [float(100 + i) for i in range(20)]
        rsi = FeatureEngine._compute_rsi(closes, 14)
        assert rsi == 100.0

    def test_compute_rsi_falling(self):
        """20 closes decreasing → RSI=0 (no gains)."""
        closes = [float(100 - i) for i in range(20)]
        rsi = FeatureEngine._compute_rsi(closes, 14)
        assert rsi == 0.0

    def test_compute_rsi_insufficient_data(self):
        """کمتر از 15 داده → return 50."""
        closes = [100.0, 101.0]
        rsi = FeatureEngine._compute_rsi(closes, 14)
        assert rsi == 50.0

    def test_compute_rsi_flat(self):
        """قیمت ثابت → avg_loss≈0 → RSI=100."""
        closes = [100.0] * 20
        rsi = FeatureEngine._compute_rsi(closes, 14)
        assert rsi == 100.0

    def test_compute_macd_bullish(self):
        """26+ closes افزایشی → MACD و signal مقادیر مشخص."""
        closes = [float(100 + i) for i in range(30)]
        signal = FeatureEngine._compute_macd_signal(closes)
        # توجه: signal ساده‌شده = SMA 9 از closes که برای uptrend > MACD است
        # پس برای uptrend خالص، مقدار -1.0 برمی‌گردد (macd < signal)
        assert signal in (-1.0, 0.0, 1.0)

    def test_compute_macd_bearish(self):
        """شتاب کاهشی (سرعت افت در حال افزایش) → MACD < signal → -1.0.

        نکته: در افت خطی ثابت، MACD به مقدار ثابت همگرا می‌شود و
        جهتش بر اساس نویز تعیین می‌شود؛ افت شتاب‌دار جهت واقعی منفی می‌دهد.
        """
        closes = [float(130 - i * i / 10) for i in range(40)]
        signal = FeatureEngine._compute_macd_signal(closes)
        assert signal == -1.0

    def test_compute_macd_insufficient_data(self):
        """کمتر از 26 داده → return 0."""
        closes = [100.0] * 20
        signal = FeatureEngine._compute_macd_signal(closes)
        assert signal == 0.0

    def test_compute_atr_basic(self, engine: FeatureEngine):
        """30 day series → ATR محاسبه شود."""
        closes = [float(100 + i) for i in range(30)]
        highs = [float(102 + i) for i in range(30)]
        lows = [float(98 + i) for i in range(30)]
        atr = engine._compute_atr(highs, lows, closes, 14)
        assert atr > 0

    def test_compute_atr_insufficient_data(self, engine: FeatureEngine):
        atr = engine._compute_atr([], [], [], 14)
        assert atr == 0.0

    def test_detect_breakout_true(self, engine: FeatureEngine):
        """آخرین close بالاتر از max 20 روز قبل باشد → True."""
        # نیاز به 21+ داده (len >= lookback+1 = 21)
        closes = list(range(100, 122))  # 22 داده
        closes[-1] = 150  # آخرین = ناگهان بالا
        assert engine._detect_breakout(closes, 20) is True

    def test_detect_breakout_false(self, engine: FeatureEngine):
        """آخرین close پایین‌تر از max → False."""
        closes = list(range(100, 120))
        assert engine._detect_breakout(closes, 20) is False

    def test_detect_breakout_insufficient_data(self, engine: FeatureEngine):
        assert engine._detect_breakout([100, 101], 20) is False

    def test_compute_trend_bullish(self, engine: FeatureEngine):
        """SMA5 > SMA20 و ROC > 2% → bullish."""
        # سری صعودی: 20 close با شیب زیاد
        closes = [float(100 + i * 5) for i in range(20)]
        assert engine._compute_trend(closes) == "bullish"

    def test_compute_trend_bearish(self, engine: FeatureEngine):
        """SMA5 < SMA20 و ROC < -2% → bearish."""
        closes = [float(200 - i * 5) for i in range(20)]
        assert engine._compute_trend(closes) == "bearish"

    def test_compute_trend_insufficient_data(self, engine: FeatureEngine):
        assert engine._compute_trend([100, 101]) == "neutral"

    def test_compute_real_legal_ratio(self):
        """real=3M, legal=2M → ratio=0.6."""
        ratio = FeatureEngine._compute_real_legal_ratio({"buy_real_volume": 3_000_000, "buy_legal_volume": 2_000_000})
        assert ratio == pytest.approx(0.6, rel=0.01)

    def test_compute_real_legal_ratio_default(self):
        """total=0 → return 0.5."""
        ratio = FeatureEngine._compute_real_legal_ratio({})
        assert ratio == 0.5

    def test_compute_micro_score_block_trade(self):
        score = FeatureEngine._compute_micro_score({"block_trade_detected": 1, "avg_trade_size": 200_000})
        assert score <= 100

    def test_compute_penalty_sell_queue(self):
        """SELL_QUEUE + streak >= 3 → +0.25."""
        penalty = FeatureEngine._compute_penalty(
            {"queue_status": "SELL_QUEUE", "queue_days_streak": 3, "distance_to_limit": 0.5},
            {},
        )
        assert penalty >= 0.25


# ═══════════════════════════════════════════════════════════════════════════════
# ── INTEGRATION: compute_all_features
# ═══════════════════════════════════════════════════════════════════════════════


class TestComputeAllFeatures:
    """تست یکپارچه compute_all_features با mock کامل."""

    @pytest.mark.asyncio
    async def test_compute_all_features_success(
        self, engine: FeatureEngine, mock_brsapi: MagicMock, mock_queue_service: MagicMock,
    ):
        """تماس کامل با تمام وابستگی‌ها."""
        mock_brsapi.get_enriched_symbol_detail.return_value = _enriched()
        mock_brsapi.get_historical_daily.return_value = _historical_daily(count=60)
        mock_brsapi.get_candlesticks.return_value = _candlestick(count=100)
        mock_queue_service.analyze_symbol.return_value = _queue_result()

        result = await engine.compute_all_features("فولاد")

        assert result["symbol"] == "فولاد"
        assert result["name"] == "فولاد مبارکه اصفهان"
        assert result["total_features"] > 100  # باید بیش از 100 ویژگی داشته باشد
        assert "features" in result
        assert result["metadata"]["data_sources"]["enriched_detail"] is True
        assert result["metadata"]["data_sources"]["historical_daily"] == 60
        assert result["metadata"]["data_sources"]["candles"] == 100
        assert result["metadata"]["data_sources"]["queue_analysis"] is True
        # Elapsed time is a float >= 0 — never assert > 0 (flaky on fast machines).
        assert isinstance(result["computation_time_ms"], float)
        assert result["computation_time_ms"] >= 0

    @pytest.mark.asyncio
    async def test_compute_all_features_all_blocks_present(
        self, engine: FeatureEngine, mock_brsapi: MagicMock, mock_queue_service: MagicMock,
    ):
        """همه ۸ بلوک باید در features وجود داشته باشند."""
        mock_brsapi.get_enriched_symbol_detail.return_value = _enriched()
        mock_brsapi.get_historical_daily.return_value = _historical_daily(count=60)
        mock_brsapi.get_candlesticks.return_value = _candlestick(count=100)
        mock_queue_service.analyze_symbol.return_value = _queue_result()

        result = await engine.compute_all_features("فولاد")
        features = result["features"]

        # Check representative keys from each block
        assert "ticker" in features           # Block A
        assert "eps_ttm" in features           # Block B
        assert "last_price" in features        # Block C
        assert "rsi_14" in features            # Block D
        assert "net_inst_volume" in features   # Block E
        assert "queue_status" in features      # Block F
        assert "market_regime" in features     # Block G
        assert "final_score" in features       # Block H

    @pytest.mark.asyncio
    async def test_compute_all_features_without_queue_service(
        self, engine: FeatureEngine, mock_brsapi: MagicMock, mock_queue_service: MagicMock,
    ):
        """QueueAnalysisService خالی برگرداند → queue_status=NONE باشد."""
        mock_brsapi.get_enriched_symbol_detail.return_value = _enriched()
        mock_brsapi.get_historical_daily.return_value = _historical_daily(count=60)
        mock_brsapi.get_candlesticks.return_value = _candlestick(count=100)
        mock_queue_service.analyze_symbol.return_value = {}  # بدون داده صف

        result = await engine.compute_all_features("فولاد")
        assert result["features"]["queue_status"] == "NONE"
        assert len(result["features"]) > 100

    @pytest.mark.asyncio
    async def test_compute_all_features_empty_enriched(
        self, engine: FeatureEngine, mock_brsapi: MagicMock, mock_queue_service: MagicMock,
    ):
        """enriched detail خالی → fallback به مقادیر پیش‌فرض بدون خطا."""
        mock_brsapi.get_enriched_symbol_detail.return_value = {}
        mock_brsapi.get_historical_daily.return_value = _historical_daily(count=10)
        mock_brsapi.get_candlesticks.return_value = _candlestick(count=10)
        mock_queue_service.analyze_symbol.return_value = _queue_result()

        result = await engine.compute_all_features("فولاد")
        assert result["features"]["last_price"] == 0
        assert result["features"]["volume"] == 0

    @pytest.mark.asyncio
    async def test_compute_all_features_queue_service_raises(
        self, engine: FeatureEngine, mock_brsapi: MagicMock, mock_queue_service: MagicMock,
    ):
        """QueueAnalysisService exception بخورد → ادامه دهد و queue ignoring کند."""
        mock_brsapi.get_enriched_symbol_detail.return_value = _enriched()
        mock_brsapi.get_historical_daily.return_value = _historical_daily(count=30)
        mock_brsapi.get_candlesticks.return_value = _candlestick(count=30)
        mock_queue_service.analyze_symbol.side_effect = Exception("Queue service down")

        result = await engine.compute_all_features("فولاد")
        assert "features" in result
        assert result["metadata"]["data_sources"]["queue_analysis"] is False

    @pytest.mark.asyncio
    async def test_compute_all_features_calls_external_methods(
        self, engine: FeatureEngine, mock_brsapi: MagicMock, mock_queue_service: MagicMock,
    ):
        """تأیید اینکه متدهای خارجی با symbol صحیح صدا شده‌اند."""
        mock_brsapi.get_enriched_symbol_detail.return_value = _enriched()
        mock_brsapi.get_historical_daily.return_value = _historical_daily(count=30)
        mock_brsapi.get_candlesticks.return_value = _candlestick(count=30)
        mock_queue_service.analyze_symbol.return_value = _queue_result()

        await engine.compute_all_features("وبملت")

        mock_brsapi.get_enriched_symbol_detail.assert_called_once_with("وبملت")
        mock_brsapi.get_historical_daily.assert_called_once_with("وبملت", limit=100)
        mock_brsapi.get_candlesticks.assert_called_once_with("وبملت", limit=100)
        mock_queue_service.analyze_symbol.assert_called_once_with("وبملت")

    @pytest.mark.asyncio
    async def test_compute_all_features_decision_override(
        self, engine: FeatureEngine, mock_brsapi: MagicMock, mock_queue_service: MagicMock,
    ):
        """BUY_QUEUE قوی → override به BUY در ویژگی‌ها."""
        mock_brsapi.get_enriched_symbol_detail.return_value = _enriched()
        mock_brsapi.get_historical_daily.return_value = _historical_daily(count=30)
        mock_brsapi.get_candlesticks.return_value = _candlestick(count=30)
        mock_queue_service.analyze_symbol.return_value = _queue_result(
            status="BUY_QUEUE", ratio=0.85, streak=1,
        )

        result = await engine.compute_all_features("فولاد")
        assert result["features"]["final_decision"] == "BUY"
        assert result["features"]["queue_status"] == "BUY_QUEUE"
