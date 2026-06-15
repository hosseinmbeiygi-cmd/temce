from __future__ import annotations


def test_quote_ohlc_consistency():
    from domain.quotes.rules import OhlcConsistencyRule

    rule = OhlcConsistencyRule()
    assert rule.validate(high=15100, low=14850, open=14900, close=15000) is True
    assert rule.validate(high=14800, low=14900, open=14900, close=15000) is False


def test_quote_positive_volume():
    from domain.quotes.rules import PositiveVolumeRule

    rule = PositiveVolumeRule()
    assert rule.validate(volume=5_000_000) is True
    assert rule.validate(volume=0) is False
    assert rule.validate(volume=-100) is False


def test_quote_price_change_consistency():
    from domain.quotes.rules import PriceChangeRule

    rule = PriceChangeRule()
    assert rule.validate(close=15000, yesterday=14900, change=100, change_pct=0.67) is True


def test_quote_max_price_change():
    from domain.quotes.rules import MaxPriceChangeRule

    rule = MaxPriceChangeRule(max_change_pct=50.0)
    assert rule.validate(change_pct=5.0) is True
    assert rule.validate(change_pct=100.0) is False


def test_quote_required_fields():
    from domain.quotes.rules import RequiredFieldsRule

    rule = RequiredFieldsRule()
    assert rule.validate(symbol="فولاد") is True
    assert rule.validate(symbol="") is False
