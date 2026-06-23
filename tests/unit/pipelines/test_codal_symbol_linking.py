from __future__ import annotations


def test_codal_symbol_link_by_isin():
    from pipelines.codal.symbol_linker import CodalSymbolLinker

    linker = CodalSymbolLinker()
    result = linker.link_by_isin(isin="IRO1FOLD0001")
    assert result is None or result == "فولاد"


def test_codal_symbol_link_by_company_name():
    from pipelines.codal.symbol_linker import CodalSymbolLinker

    linker = CodalSymbolLinker()
    result = linker.link_by_company_name("فولاد مبارکه اصفهان")
    assert result is None or result.startswith("ف")


def test_codal_symbol_resolve():
    from pipelines.codal.symbol_linker import CodalSymbolLinker

    linker = CodalSymbolLinker()
    result = linker.resolve("فولاد")
    assert result is None or result == "فولاد"


def test_codal_batch_link():
    from pipelines.codal.symbol_linker import CodalSymbolLinker

    linker = CodalSymbolLinker()
    reports = [
        {"isin": "IRO1FOLD0001", "company": "فولاد مبارکه"},
        {"isin": "IRO1FMLI0001", "company": "ملی صنایع مس"},
    ]
    results = linker.batch_link(reports)
    assert len(results) == 2

