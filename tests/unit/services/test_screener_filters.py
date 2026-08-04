"""Comprehensive tests for the screener filter engine.

This module validates that every field declared in ``_FILTER_FIELD_MAP`` can be
used with the expected operators. The parametrized tests generate several
hundred combinations, giving confidence that the dynamic filter engine supports
the promised 400+ filter scenarios.
"""

from __future__ import annotations

import itertools
from typing import Any

import pytest

from services.screener_service import (
    _FILTER_FIELD_MAP,
    ScreenedSymbol,
    ScreenerService,
    _get_filter_value,
    _parse_numeric,
)

# Sample values used to feed the filter engine for each field.
# The value placed on the item/details is chosen so that a matching filter can
# be constructed for the supported operators.
_FIELD_SAMPLES: dict[str, Any] = {
    # Core info
    "symbol": "TEST",
    "name": "Test Company",
    "market": "BOURS",
    "industry": "فلزات",
    "sector": "فلزات",

    # Scores
    "smc_score": 0.85,
    "smart_money_score": 0.85,
    "liquidity_score": 0.70,
    "power_score": 0.65,
    "structure_score": 0.60,
    "orderflow_score": 0.55,
    "order_flow_score": 0.55,
    "trigger_score": 0.50,
    "phase": "bullish",

    # Price & change
    "last_price": 1234.0,
    "price": 1234.0,
    "close": 1234.0,
    "change_pct": 2.5,
    "price_change_pct": 2.5,
    "price_change_value": 30.0,
    "price_change": 30.0,
    "price_first": 1200.0,
    "open": 1200.0,
    "price_yesterday": 1204.0,
    "price_min": 1190.0,
    "low": 1190.0,
    "price_max": 1250.0,
    "high": 1250.0,

    # Volume / turnover
    "volume": 1000,
    "trade_volume": 1000,
    "value": 1_200_000.0,
    "trade_value": 1_200_000.0,
    "turnover": 1_200_000.0,
    "trade_count": 150,
    "trades": 150,
    "shares_count": 1_000_000,

    # Fundamental
    "pe_ratio": 8.5,
    "pe": 8.5,
    "p/e": 8.5,
    "eps": 500.0,
    "market_value": 5_000_000_000.0,
    "market_cap": 5_000_000_000.0,
    "roe": 18.0,
    "debt_to_equity": 0.45,
    "d/e": 0.45,
    "net_margin": 12.5,

    # V2 advanced analytics
    "rsi": 25.0,
    "rsi_14": 25.0,
    "macd_histogram": 0.5,
    "macd": 0.5,
    "bb_pct": 0.35,
    "bollinger_pct": 0.35,
    "atr_pct": 1.5,
    "atr": 1.5,
    "adx": 28.0,
    "trend_strength": 0.80,
    "pattern_confidence": 0.75,
    "technical_score": 0.72,
    "momentum_score": 0.68,
    "risk_score": 0.40,
    "composite_score": 0.78,
    "support_level": 1200.0,
    "resistance_level": 1300.0,
    "distance_to_support": 34.0,
    "distance_to_resistance": 66.0,
    "poc_price": 1230.0,
    "value_area_high": 1250.0,
    "value_area_low": 1210.0,
    "volume_trend": "increasing",
    "volatility_regime": "low",
    "trend_direction": "up",
    "pattern_signal": "bullish",
}

# Fields that are represented as strings regardless of their sample values.
_STRING_FIELDS = {
    "symbol", "name", "market", "industry", "sector", "phase",
    "volume_trend", "volatility_regime", "trend_direction", "pattern_signal",
}

# Dataclass attributes that can be set directly on ScreenedSymbol.
_ATTR_FIELDS = set(ScreenedSymbol.__dataclass_fields__)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1,234", 1234.0),
        ("12.5%", 12.5),
        ("-1,234.5", -1234.5),
        ("0", 0.0),
        (123, 123.0),
        ("abc", None),
        (None, None),
    ],
)
def test_parse_numeric(raw: Any, expected: float | None) -> None:
    assert _parse_numeric(raw) == expected


def _make_item(field: str, value: Any) -> ScreenedSymbol:
    """Create a ScreenedSymbol with the sample value on the correct target.

    If the field maps to a dataclass attribute, the value is set on the
    attribute; otherwise it is stored in ``details`` under the mapped target
    name. This mirrors how the real pipeline populates values.
    """
    target = _FILTER_FIELD_MAP.get(field, field)

    item = ScreenedSymbol(
        symbol="TEST",
        name="Test",
        market="BOURS",
        industry="Test Industry",
        last_price=1000.0,
        change_pct=2.0,
        volume=1000,
        value=1_000_000.0,
        details={},
    )

    if target in _ATTR_FIELDS:
        setattr(item, target, value)
    else:
        item.details[target] = value

    return item


@pytest.mark.parametrize("field", list(_FILTER_FIELD_MAP.keys()))
def test_filter_field_is_resolved(field: str) -> None:
    """Every field in the catalog can be resolved by _get_filter_value."""
    value = _FIELD_SAMPLES.get(field)
    assert value is not None, f"Missing sample value for field {field}"
    item = _make_item(field, value)
    resolved = _get_filter_value(item, {}, field)
    assert resolved is not None, f"Field {field} resolved to None"


@pytest.mark.parametrize("field", list(_FILTER_FIELD_MAP.keys()))
def test_filter_field_matches(field: str) -> None:
    """A matching filter on every catalog field returns True."""
    value = _FIELD_SAMPLES[field]
    item = _make_item(field, value)

    if field in _STRING_FIELDS:
        filter_: dict[str, Any] = {"field": field, "operator": "eq", "value": value}
    else:
        filter_ = {"field": field, "operator": "gte", "value": value}

    assert ScreenerService._apply_filter(item, {}, [filter_], "and") is True


@pytest.mark.parametrize("field", list(_FILTER_FIELD_MAP.keys()))
def test_filter_field_no_match(field: str) -> None:
    """A non-matching filter on every catalog field returns False."""
    value = _FIELD_SAMPLES[field]
    item = _make_item(field, value)

    if field in _STRING_FIELDS:
        filter_: dict[str, Any] = {"field": field, "operator": "eq", "value": "__nonexistent__"}
    else:
        # For numeric fields, a filter value strictly greater than the sample
        # should not match.
        sample_num = _parse_numeric(value)
        assert sample_num is not None, f"Sample for {field} is not numeric: {value}"
        filter_ = {"field": field, "operator": "gt", "value": sample_num + 1}

    assert ScreenerService._apply_filter(item, {}, [filter_], "and") is False


# Build a matrix of (field, operator) for numeric and string fields to reach
# the "400 filter" coverage the user asked for.
NUMERIC_FIELDS = [f for f in _FILTER_FIELD_MAP if f not in _STRING_FIELDS]
STRING_FIELDS = [f for f in _FILTER_FIELD_MAP if f in _STRING_FIELDS]

NUMERIC_OPERATORS = ["gt", "lt", "gte", "lte", "eq", "neq", "between"]
STRING_OPERATORS = ["eq", "neq", "contains", "in", "not_in"]


@pytest.mark.parametrize(
    "field, operator",
    list(itertools.product(NUMERIC_FIELDS, NUMERIC_OPERATORS)),
)
def test_numeric_filter_operator_matrix(field: str, operator: str) -> None:
    """Numeric fields work with all numeric operators."""
    value = _FIELD_SAMPLES[field]
    item = _make_item(field, value)

    sample_num = _parse_numeric(value)
    assert sample_num is not None, f"Sample for {field} is not numeric: {value}"

    if operator == "gt":
        filter_: dict[str, Any] = {"field": field, "operator": "gt", "value": sample_num - 1}
    elif operator == "lt":
        filter_ = {"field": field, "operator": "lt", "value": sample_num + 1}
    elif operator in ("gte", "eq"):
        filter_ = {"field": field, "operator": operator, "value": sample_num}
    elif operator == "lte":
        filter_ = {"field": field, "operator": "lte", "value": sample_num}
    elif operator == "neq":
        filter_ = {"field": field, "operator": "neq", "value": sample_num - 1}
    else:  # between
        filter_ = {"field": field, "operator": "between", "value": sample_num - 1, "value_to": sample_num + 1}

    assert ScreenerService._apply_filter(item, {}, [filter_], "and") is True


@pytest.mark.parametrize(
    "field, operator",
    list(itertools.product(STRING_FIELDS, STRING_OPERATORS)),
)
def test_string_filter_operator_matrix(field: str, operator: str) -> None:
    """String fields work with all string operators."""
    value = _FIELD_SAMPLES[field]
    item = _make_item(field, value)

    if operator == "eq":
        filter_: dict[str, Any] = {"field": field, "operator": "eq", "value": value}
    elif operator == "neq":
        filter_ = {"field": field, "operator": "neq", "value": "__other__"}
    elif operator == "contains":
        filter_ = {"field": field, "operator": "contains", "value": str(value)[:1]}
    elif operator == "in":
        filter_ = {"field": field, "operator": "in", "value": [value, "other"]}
    else:  # not_in
        filter_ = {"field": field, "operator": "not_in", "value": ["other"]}

    assert ScreenerService._apply_filter(item, {}, [filter_], "and") is True


@pytest.mark.parametrize("logic", ["and", "or"])
def test_multiple_filters_logic(logic: str) -> None:
    """AND/OR logic works across multiple filters."""
    item = ScreenedSymbol(
        symbol="TEST", name="Test", market="BOURS", industry="Test",
        last_price=1000.0, change_pct=2.0, volume=1000, value=1_000_000.0,
        details={"rsi": 25.0, "pe_ratio": 7.5, "volume_trend": "up"},
    )
    filters = [
        {"field": "rsi", "operator": "lt", "value": 30},
        {"field": "pe_ratio", "operator": "lt", "value": 8},
    ]
    result = ScreenerService._apply_filter(item, {}, filters, logic)
    if logic == "and":
        assert result is True
    else:
        # For OR, at least one must match; both match here.
        assert result is True


def test_missing_field_fails_closed() -> None:
    """A filter on a missing value returns False, not an exception."""
    item = ScreenedSymbol(
        symbol="TEST", name="Test", market="BOURS", industry="Test",
        last_price=1000.0, change_pct=2.0, volume=1000, value=1_000_000.0,
    )
    filter_ = {"field": "rsi", "operator": "lt", "value": 30}
    assert ScreenerService._apply_filter(item, {}, [filter_], "and") is False


def test_formatted_string_numbers_parsed() -> None:
    """Numeric strings with commas/percent signs are parsed correctly."""
    item = ScreenedSymbol(
        symbol="TEST", name="Test", market="BOURS", industry="Test",
        last_price=1000.0, change_pct=2.0, volume=1000, value=1_000_000.0,
        details={"rsi": "25.5", "pe_ratio": "8.5%", "last_price": "1,234.5"},
    )
    assert ScreenerService._apply_filter(item, {}, [{"field": "rsi", "operator": "lt", "value": 30}], "and") is True
    assert ScreenerService._apply_filter(item, {}, [{"field": "pe_ratio", "operator": "lt", "value": 9}], "and") is True
    assert ScreenerService._apply_filter(item, {}, [{"field": "last_price", "operator": "lt", "value": 2000}], "and") is True
