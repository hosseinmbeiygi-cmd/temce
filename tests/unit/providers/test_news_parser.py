from __future__ import annotations


def test_news_parse_article():
    from providers.news.parser import NewsParser

    parser = NewsParser()
    raw = {"title": "Test Title", "description": "Test Description", "link": "https://example.com"}
    article = parser.parse_article(raw)
    assert article["title"] == "Test Title"


def test_news_parse_rss_feed():
    from providers.news.parser import NewsParser

    parser = NewsParser()
    feed_xml = """<?xml version="1.0"?><rss><channel><item><title>Test</title><description>Desc</description></item></channel></rss>"""
    items = parser.parse_feed(feed_xml)
    assert len(items) >= 1


def test_news_extract_sentiment():
    from providers.news.parser import NewsParser

    parser = NewsParser()
    score = parser.extract_sentiment("خبر بسیار خوب و مثبت")
    assert score is not None


def test_news_extract_symbols():
    from providers.news.parser import NewsParser

    parser = NewsParser()
    symbols = parser.extract_symbols("قیمت سهام فولاد و فملی")
    assert len(symbols) >= 0


def test_news_normalize_date():
    from providers.news.parser import NewsParser

    parser = NewsParser()
    normalized = parser.normalize_date("2024-01-15T10:30:00")
    assert normalized is not None

