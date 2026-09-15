"""Unit tests for fund API adapter — validation, quarantine, date parsing."""

from __future__ import annotations

from datetime import date

from services.fund_api_adapter import (
    normalize_date,
    parse_gregorian,
    parse_jalali,
    validate_holding,
    validate_nav_record,
    validate_portfolio_weights,
    validate_quote,
)

# ── Date parsing (شمسی/میلادی ساخت‌یافته) ───────────────────────────────────


def test_parse_jalali_standard():
    assert parse_jalali("1403/05/12") == date(2024, 8, 2)


def test_parse_jalali_persian_digits():
    assert parse_jalali("۱۴۰۳/۰۵/۱۲") == date(2024, 8, 2)


def test_parse_jalali_invalid_month():
    assert parse_jalali("1403/13/05") is None
    assert parse_jalali("not-a-date") is None
    assert parse_jalali("") is None
    assert parse_jalali(None) is None


def test_parse_gregorian():
    assert parse_gregorian("2024-08-02") == date(2024, 8, 2)
    assert parse_gregorian("2024/13/01") is None


def test_normalize_date_auto_detect():
    assert normalize_date("1403/05/12") == date(2024, 8, 2)
    assert normalize_date("2024-08-02") == date(2024, 8, 2)


# ── NAV validation ───────────────────────────────────────────────────────────


def test_nav_valid():
    rec = {"nav_issue": 12_500.0, "nav_redemption": 12_000.0, "nav_date": date(2024, 8, 2)}
    assert validate_nav_record(rec).ok is True


def test_nav_negative_rejected():
    rec = {"nav_issue": -5.0, "nav_date": date(2024, 8, 2)}
    v = validate_nav_record(rec)
    assert v.ok is False
    assert v.rule == "nav_non_positive"


def test_nav_missing_date_rejected():
    rec = {"nav_issue": 100.0}
    v = validate_nav_record(rec)
    assert v.ok is False
    assert v.rule == "nav_date_invalid"


# ── Holding validation ───────────────────────────────────────────────────────


def test_holding_weight_out_of_range():
    rec = {"holding_type": "equity", "instrument_symbol": "فولاد", "weight_pct": 150.0}
    v = validate_holding(rec)
    assert v.ok is False
    assert v.rule == "holding_weight_range"


def test_holding_negative_value():
    rec = {"holding_type": "equity", "instrument_symbol": "X", "market_value": -100}
    assert validate_holding(rec).ok is False


def test_equity_holding_without_symbol():
    rec = {"holding_type": "equity", "weight_pct": 5.0}
    v = validate_holding(rec)
    assert v.ok is False
    assert v.rule == "holding_symbol_missing"


def test_valid_holding():
    rec = {"holding_type": "deposit", "instrument_name": "سپرده", "weight_pct": 10.0}
    assert validate_holding(rec).ok is True


# ── Portfolio weight sum ─────────────────────────────────────────────────────


def test_weights_sum_within_tolerance():
    holdings = [
        {"weight_pct": 40.0},
        {"weight_pct": 35.0},
        {"weight_pct": 25.0},
    ]
    assert validate_portfolio_weights(holdings).ok is True


def test_weights_sum_out_of_tolerance():
    holdings = [{"weight_pct": 60.0}, {"weight_pct": 60.0}]  # جمع ۱۲۰
    v = validate_portfolio_weights(holdings)
    assert v.ok is False
    assert v.rule == "portfolio_weight_sum"


def test_weights_sum_allows_debt_tolerance():
    # جمع ۹۸٪ در تلورانس ±۳٪ مجاز
    assert validate_portfolio_weights([{"weight_pct": 98.0}]).ok is True


# ── Quote validation ─────────────────────────────────────────────────────────


def test_quote_zero_price_rejected():
    v = validate_quote({"last_price": 0.0, "close_price": 0.0})
    assert v.ok is False
    assert v.rule == "quote_price_invalid"


def test_quote_negative_volume_rejected():
    assert validate_quote({"last_price": 1000, "trade_volume": -5}).ok is False


def test_quote_valid():
    assert validate_quote({"last_price": 12_500, "trade_volume": 1000}).ok is True
