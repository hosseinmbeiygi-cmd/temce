"""Tests for screener NLU filter extraction and filter field catalog."""

from __future__ import annotations

from services.screener_service import _FILTER_FIELD_MAP, ScreenedSymbol, _get_filter_value
from services.unified_assistant_service import (
    _detect_filter_logic,
    _extract_screener_filters,
)


class TestScreenerFilterExtraction:
    """Test extraction of filter criteria from Persian/English text."""

    def test_oversold_rsi(self) -> None:
        filters = _extract_screener_filters("سهم‌های اشباع فروش رو نشون بده")
        assert any(f["field"] == "rsi" and f["operator"] == "lt" and f["value"] == 30 for f in filters)

    def test_overbought_rsi(self) -> None:
        filters = _extract_screener_filters("نمادهای با rsi بالا")
        assert any(f["field"] == "rsi" and f["operator"] == "gt" and f["value"] == 70 for f in filters)

    def test_volume_filter(self) -> None:
        filters = _extract_screener_filters("سهام پرحجم")
        assert any(f["field"] == "volume" and f["operator"] == "gt" for f in filters)

    def test_smart_money(self) -> None:
        filters = _extract_screener_filters("سهام با پول هوشمند")
        assert any(f["field"] == "smc_score" and f["operator"] == "gt" for f in filters)

    def test_numeric_pattern(self) -> None:
        filters = _extract_screener_filters("فیلتر RSI<30 P/E<8")
        assert len([f for f in filters if f["field"] == "rsi" and f["value"] == 30.0]) == 1
        assert len([f for f in filters if f["field"] == "pe_ratio" and f["value"] == 8.0]) == 1

    def test_no_duplicate_filters(self) -> None:
        # "اشباع فروش" maps to rsi<30; numeric "RSI<30" also maps to rsi<30
        filters = _extract_screener_filters("سهم‌های اشباع فروش RSI<30")
        rsi_filters = [f for f in filters if f["field"] == "rsi"]
        assert len(rsi_filters) == 1


# ── Numeric pattern tests for new indicator fields ─────────────────────


class TestNumericPatternMACD:
    def test_macd_positive(self) -> None:
        filters = _extract_screener_filters("MACD>0")
        assert any(f["field"] == "macd_histogram" and f["operator"] == "gt" and f["value"] == 0.0 for f in filters)

    def test_macd_negative(self) -> None:
        filters = _extract_screener_filters("MACD<-5")
        assert any(f["field"] == "macd_histogram" and f["operator"] == "lt" and f["value"] == -5.0 for f in filters)

    def test_macd_persian_synonym(self) -> None:
        filters = _extract_screener_filters("ماکد مثبت")
        assert any(f["field"] == "macd_histogram" and f["operator"] == "gt" for f in filters)

    def test_macd_divergence_persian(self) -> None:
        filters = _extract_screener_filters("واگرایی مثبت")
        assert any(f["field"] == "macd_histogram" and f["operator"] == "gt" for f in filters)


class TestNumericPatternADX:
    def test_adx_strong(self) -> None:
        filters = _extract_screener_filters("ADX>25")
        assert any(f["field"] == "adx" and f["operator"] == "gt" and f["value"] == 25.0 for f in filters)

    def test_adx_weak(self) -> None:
        filters = _extract_screener_filters("ADX<20")
        assert any(f["field"] == "adx" and f["operator"] == "lt" and f["value"] == 20.0 for f in filters)

    def test_adx_persian_synonym(self) -> None:
        filters = _extract_screener_filters("ترند قوی")
        assert any(f["field"] == "adx" and f["operator"] == "gt" for f in filters)

    def test_adx_trend_strength_pattern(self) -> None:
        filters = _extract_screener_filters("trend strength>30")
        assert any(f["field"] == "adx" and f["value"] == 30.0 for f in filters)


class TestNumericPatternCCI:
    def test_cci_overbought(self) -> None:
        filters = _extract_screener_filters("CCI>100")
        assert any(f["field"] == "cci" and f["operator"] == "gt" and f["value"] == 100.0 for f in filters)

    def test_cci_oversold(self) -> None:
        filters = _extract_screener_filters("CCI<-100")
        assert any(f["field"] == "cci" and f["operator"] == "lt" and f["value"] == -100.0 for f in filters)

    def test_cci_negative(self) -> None:
        filters = _extract_screener_filters("cci<-50")
        assert any(f["field"] == "cci" and f["value"] == -50.0 for f in filters)

    def test_cci_persian_synonym(self) -> None:
        filters = _extract_screener_filters("cci اشباع فروش")
        assert any(f["field"] == "cci" and f["operator"] == "lt" and f["value"] == -100 for f in filters)


class TestNumericPatternMFI:
    def test_mfi_high(self) -> None:
        filters = _extract_screener_filters("MFI>80")
        assert any(f["field"] == "mfi" and f["operator"] == "gt" and f["value"] == 80.0 for f in filters)

    def test_mfi_low(self) -> None:
        filters = _extract_screener_filters("MFI<20")
        assert any(f["field"] == "mfi" and f["operator"] == "lt" and f["value"] == 20.0 for f in filters)

    def test_mfi_persian_synonym(self) -> None:
        filters = _extract_screener_filters("mfi اشباع خرید")
        assert any(f["field"] == "mfi" and f["operator"] == "gt" and f["value"] == 80 for f in filters)


class TestNumericPatternWilliams:
    def test_williams_oversold(self) -> None:
        filters = _extract_screener_filters("williams<-80")
        assert any(f["field"] == "williams_r" and f["operator"] == "lt" and f["value"] == -80.0 for f in filters)

    def test_williams_overbought(self) -> None:
        filters = _extract_screener_filters("williams%r>-20")
        assert any(f["field"] == "williams_r" and f["operator"] == "gt" and f["value"] == -20.0 for f in filters)

    def test_williams_persian(self) -> None:
        filters = _extract_screener_filters("ویلیامز اشباع فروش")
        assert any(f["field"] == "williams_r" and f["operator"] == "lt" and f["value"] == -80 for f in filters)


class TestNumericPatternStochastic:
    def test_stochastic_low(self) -> None:
        filters = _extract_screener_filters("stochastic<20")
        assert any(f["field"] == "stochastic_k" and f["operator"] == "lt" and f["value"] == 20.0 for f in filters)

    def test_sto_high(self) -> None:
        filters = _extract_screener_filters("sto>80")
        assert any(f["field"] == "stochastic_k" and f["operator"] == "gt" and f["value"] == 80.0 for f in filters)

    def test_stochastic_persian(self) -> None:
        filters = _extract_screener_filters("استوکاستیک پایین")
        assert any(f["field"] == "stochastic_k" and f["operator"] == "lt" and f["value"] == 20 for f in filters)


class TestNumericPatternBB:
    def test_bb_percentage(self) -> None:
        filters = _extract_screener_filters("BB>0.8")
        assert any(f["field"] == "bb_pct" and f["operator"] == "gt" and f["value"] == 0.8 for f in filters)

    def test_bollinger_persian(self) -> None:
        filters = _extract_screener_filters("بولینگر پایین")
        assert any(f["field"] == "bb_pct" and f["operator"] == "lt" for f in filters)

    def test_bb_squeeze(self) -> None:
        filters = _extract_screener_filters("bb squeeze")
        assert any(f["field"] == "atr_pct" and f["operator"] == "lt" and f["value"] == 0.02 for f in filters)


class TestNumericPatternATR:
    def test_atr_high_volatility(self) -> None:
        filters = _extract_screener_filters("ATR>5")
        assert any(f["field"] == "atr_pct" and f["operator"] == "gt" and f["value"] == 5.0 for f in filters)

    def test_atr_persian(self) -> None:
        filters = _extract_screener_filters("نوسان شدید")
        assert any(f["field"] == "atr_pct" and f["operator"] == "gt" and f["value"] == 0.04 for f in filters)


class TestNumericPatternFundamental:
    def test_eps_negative(self) -> None:
        filters = _extract_screener_filters("eps<0")
        assert any(f["field"] == "eps" and f["operator"] == "lt" and f["value"] == 0.0 for f in filters)

    def test_market_cap_large(self) -> None:
        filters = _extract_screener_filters("market cap>10000000000000")
        assert any(f["field"] == "market_value" and f["operator"] == "gt" for f in filters)

    def test_debt_to_equity_pattern(self) -> None:
        filters = _extract_screener_filters("d/e>1.5")
        assert any(f["field"] == "debt_to_equity" and f["value"] == 1.5 for f in filters)

    def test_net_margin_pattern(self) -> None:
        filters = _extract_screener_filters("net margin>20")
        assert any(f["field"] == "net_margin" and f["value"] == 20.0 for f in filters)


class TestNumericPatternComposite:
    def test_technical_score(self) -> None:
        filters = _extract_screener_filters("technical score>0.7")
        assert any(f["field"] == "technical_score" and f["value"] == 0.7 for f in filters)

    def test_composite_score(self) -> None:
        filters = _extract_screener_filters("composite score>0.5")
        assert any(f["field"] == "composite_score" and f["value"] == 0.5 for f in filters)

    def test_risk_score(self) -> None:
        filters = _extract_screener_filters("risk score<0.3")
        assert any(f["field"] == "risk_score" and f["value"] == 0.3 for f in filters)

    def test_pattern_confidence(self) -> None:
        filters = _extract_screener_filters("pattern confidence>0.6")
        assert any(f["field"] == "pattern_confidence" and f["value"] == 0.6 for f in filters)


class TestNumericPatternSupportResistance:
    def test_support_level(self) -> None:
        filters = _extract_screener_filters("support>1000")
        assert any(f["field"] == "support_level" and f["value"] == 1000.0 for f in filters)

    def test_resistance_level(self) -> None:
        filters = _extract_screener_filters("resistance<5000")
        assert any(f["field"] == "resistance_level" and f["value"] == 5000.0 for f in filters)

    def test_poc_price(self) -> None:
        filters = _extract_screener_filters("poc>2000")
        assert any(f["field"] == "poc_price" and f["value"] == 2000.0 for f in filters)

    def test_trade_count(self) -> None:
        filters = _extract_screener_filters("trade count>1000")
        assert any(f["field"] == "trade_count" and f["value"] == 1000.0 for f in filters)


class TestPersianSynonymNewIndicators:
    """Test new Persian synonym phrases for indicators."""

    def test_macd_persian(self) -> None:
        filters = _extract_screener_filters("ماکد صعودی")
        assert any(f["field"] == "macd_histogram" and f["operator"] == "gt" for f in filters)

    def test_cci_persian(self) -> None:
        filters = _extract_screener_filters("cci صعودی")
        assert any(f["field"] == "cci" and f["operator"] == "gt" for f in filters)

    def test_mfi_strong(self) -> None:
        filters = _extract_screener_filters("mfi قوی")
        assert any(f["field"] == "mfi" and f["operator"] == "gt" and f["value"] == 50 for f in filters)

    def test_williams_persian_short(self) -> None:
        filters = _extract_screener_filters("ویلیامز بالا")
        assert any(f["field"] == "williams_r" and f["operator"] == "gt" for f in filters)

    def test_stochastic_persian_high(self) -> None:
        filters = _extract_screener_filters("استوکاستیک بالا")
        assert any(f["field"] == "stochastic_k" and f["operator"] == "gt" and f["value"] == 80 for f in filters)

    def test_no_risk_persian(self) -> None:
        filters = _extract_screener_filters("کم‌ریسک")
        assert any(f["field"] == "risk_score" and f["operator"] == "lt" and f["value"] == 0.3 for f in filters)

    def test_safe_persian(self) -> None:
        filters = _extract_screener_filters("ایمن")
        assert any(f["field"] == "risk_score" and f["operator"] == "lt" and f["value"] == 0.3 for f in filters)

    def test_near_support_persian(self) -> None:
        filters = _extract_screener_filters("نزدیک حمایت")
        assert any(f["field"] == "distance_to_support" and f["operator"] == "lt" and f["value"] == 0.02 for f in filters)

    def test_breakout_persian(self) -> None:
        filters = _extract_screener_filters("شکست مقاومت")
        assert any(f["field"] == "distance_to_resistance" for f in filters)

    def test_eps_persian(self) -> None:
        filters = _extract_screener_filters("زیان‌ده")
        assert any(f["field"] == "eps" and f["operator"] == "lt" and f["value"] == 0 for f in filters)

    def test_low_volatility_persian(self) -> None:
        filters = _extract_screener_filters("آرام")
        assert any(f["field"] == "atr_pct" and f["operator"] == "lt" for f in filters)

    def test_market_no_trend_persian(self) -> None:
        filters = _extract_screener_filters("بازار خنثی")
        assert any(f["field"] == "adx" and f["operator"] == "lt" and f["value"] == 20 for f in filters)


class TestFilterLogicDetection:
    """Test AND/OR logic detection from screener query text."""

    def test_default_logic_is_and(self) -> None:
        assert _detect_filter_logic("سهام پرحجم با RSI کمتر از 30") == "and"

    def test_persian_or(self) -> None:
        assert _detect_filter_logic("سهام پرحجم یا RSI کمتر از 30") == "or"

    def test_english_or(self) -> None:
        assert _detect_filter_logic("high volume or rsi below 30") == "or"

    def test_case_insensitive_english_or(self) -> None:
        assert _detect_filter_logic("High Volume OR RSI below 30") == "or"

    def test_persian_and(self) -> None:
        assert _detect_filter_logic("سهام پرحجم و RSI کمتر از 30") == "and"

    def test_or_inside_word_does_not_trigger(self) -> None:
        # "for" contains "or" but should not be treated as OR logic.
        assert _detect_filter_logic("search for stocks with rsi below 30") == "and"

    def test_persian_comma_before_or(self) -> None:
        assert _detect_filter_logic("RSI<30، یا حجم بالا") == "or"

    def test_mixed_and_or_prefers_or(self) -> None:
        assert _detect_filter_logic("سهام پرحجم و RSI بالا یا P/E کم") == "or"


class TestFilterFieldMap:
    """Test the comprehensive filter field catalog."""

    def test_all_v2_fields_mapped(self) -> None:
        v2_fields = [
            "rsi", "macd_histogram", "bb_pct", "atr_pct", "adx",
            "trend_strength", "pattern_confidence", "technical_score",
            "momentum_score", "risk_score", "composite_score",
            "support_level", "resistance_level", "distance_to_support",
            "distance_to_resistance", "poc_price", "value_area_high",
            "value_area_low", "volume_trend", "volatility_regime",
            "trend_direction", "pattern_signal",
        ]
        for field in v2_fields:
            assert field in _FILTER_FIELD_MAP, f"V2 field {field} missing from catalog"

    def test_get_filter_value_from_symbol(self) -> None:
        item = ScreenedSymbol(
            symbol="TEST", name="Test", market="BOURS", industry="Test",
            last_price=100.0, change_pct=2.0, volume=1000, value=100000.0,
        )
        watch: dict = {}
        assert _get_filter_value(item, watch, "symbol") == "TEST"
        assert _get_filter_value(item, watch, "volume") == 1000.0

    def test_get_filter_value_from_details(self) -> None:
        item = ScreenedSymbol(
            symbol="TEST", name="Test", market="BOURS", industry="Test",
            last_price=100.0, change_pct=2.0, volume=1000, value=100000.0,
            details={"rsi": 25.0, "trend_direction": "up"},
        )
        watch: dict = {}
        assert _get_filter_value(item, watch, "rsi") == 25.0
        assert _get_filter_value(item, watch, "trend_direction") == "up"
