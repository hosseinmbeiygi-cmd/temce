from __future__ import annotations


def test_quote_validator_required_fields():
    from pipelines.quotes.validator import QuoteValidator

    validator = QuoteValidator()
    valid = {"symbol": "فولاد", "price_close": 15000, "volume": 5000000, "date": "2024-01-15"}
    assert validator.validate(valid) is True


def test_quote_validator_missing_fields():
    from pipelines.quotes.validator import QuoteValidator

    validator = QuoteValidator()
    invalid = {"price_close": 15000}
    assert validator.validate(invalid) is False


def test_quote_validator_price_range():
    from pipelines.quotes.validator import QuoteValidator

    validator = QuoteValidator()
    assert validator.validate_field("price_close", 15000) is True
    assert validator.validate_field("price_close", -100) is False


def test_quote_validator_date_format():
    from pipelines.quotes.validator import QuoteValidator

    validator = QuoteValidator()
    assert validator.validate_field("date", "2024-01-15") is True
    assert validator.validate_field("date", "15-01-2024") is False


def test_quote_validator_ohlc():
    from pipelines.quotes.validator import QuoteValidator

    validator = QuoteValidator()
    valid_ohlc = {"high": 15100, "low": 14850, "open": 14900, "close": 15000}
    invalid_ohlc = {"high": 14800, "low": 14900, "open": 14900, "close": 15000}
    assert validator.validate_ohlc(**valid_ohlc) is True
    assert validator.validate_ohlc(**invalid_ohlc) is False
