from __future__ import annotations


def test_macro_parse_inflation():
    from providers.macro.parser import MacroParser

    parser = MacroParser()
    result = parser.parse_inflation({"value": "42.5", "date": "1402-10"})
    assert result["value"] == 42.5


def test_macro_parse_unemployment():
    from providers.macro.parser import MacroParser

    parser = MacroParser()
    result = parser.parse_unemployment({"value": "9.2", "date": "1402-09"})
    assert result["value"] == 9.2


def test_macro_parse_gdp():
    from providers.macro.parser import MacroParser

    parser = MacroParser()
    result = parser.parse_gdp({"value": "4.5", "date": "1402"})
    assert result["value"] == 4.5


def test_macro_parse_date():
    from providers.macro.parser import MacroParser

    parser = MacroParser()
    assert parser.parse_date("1402-10") == "1402-10"
    assert parser.parse_date("1402") == "1402"


def test_macro_format_value():
    from providers.macro.parser import MacroParser

    parser = MacroParser()
    assert parser.format_value(42.5, "percent") == 42.5
    assert parser.format_value(2500000000000, "rial") == 2500000000000
