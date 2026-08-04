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
