from __future__ import annotations


def test_news_symbol_extraction():
    from pipelines.news.symbol_linker import NewsSymbolLinker

    linker = NewsSymbolLinker()
    text = "قیمت سهام فولاد و فملی امروز افزایش یافت"
    symbols = linker.extract_symbols(text)
    assert "فولاد" in symbols
    assert "فملی" in symbols


def test_news_symbol_link():
    from pipelines.news.symbol_linker import NewsSymbolLinker

    linker = NewsSymbolLinker()
    article = {"title": "افزایش قیمت فولاد", "content": "شرکت فولاد مبارکه"}
    linked = linker.link_symbols(article)
    assert "symbols" in linked


def test_news_batch_link():
    from pipelines.news.symbol_linker import NewsSymbolLinker

    linker = NewsSymbolLinker()
    articles = [
        {"title": "خبر اول", "content": "قیمت فولاد"},
        {"title": "خبر دوم", "content": "قیمت فملی و وبانک"},
    ]
    results = linker.batch_link(articles)
    assert len(results) == 2


def test_news_no_symbol_match():
    from pipelines.news.symbol_linker import NewsSymbolLinker

    linker = NewsSymbolLinker()
    text = "متن بدون نماد بورسی"
    symbols = linker.extract_symbols(text)
    assert len(symbols) == 0
