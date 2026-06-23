from __future__ import annotations


def test_instrument_symbol_required():
    from domain.instruments.rules import SymbolRequiredRule

    rule = SymbolRequiredRule()
    assert rule.validate(symbol="فولاد") is True
    assert rule.validate(symbol="") is False


def test_instrument_isin_format():
    from domain.instruments.rules import IsinFormatRule

    rule = IsinFormatRule()
    assert rule.validate(isin="IRO1FOLD0001") is True
    assert rule.validate(isin="invalid") is False


def test_instrument_market_type():
    from domain.instruments.rules import MarketTypeRule

    rule = MarketTypeRule(allowed_types=["bours", "farabours"])
    assert rule.validate(market_type="bours") is True
    assert rule.validate(market_type="invalid") is False


def test_instrument_positive_par_value():
    from domain.instruments.rules import ParValueRule

    rule = ParValueRule()
    assert rule.validate(par_value=1000) is True
    assert rule.validate(par_value=0) is False
    assert rule.validate(par_value=-100) is False


def test_instrument_unique_symbol():
    from domain.instruments.rules import UniqueSymbolRule

    rule = UniqueSymbolRule(existing_symbols=["فولاد", "فملی"])
    assert rule.validate(symbol="خودرو") is True
    assert rule.validate(symbol="فولاد") is False

