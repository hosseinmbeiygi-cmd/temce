from __future__ import annotations


def test_quote_normalize_price():
    from pipelines.quotes.normalizer import QuoteNormalizer

    normalizer = QuoteNormalizer()
    normalized = normalizer.normalize_price(15000)
    assert isinstance(normalized, float)


def test_quote_normalize_volume():
    from pipelines.quotes.normalizer import QuoteNormalizer

    normalizer = QuoteNormalizer()
    normalized = normalizer.normalize_volume(5000000)
    assert normalized == 5.0


def test_quote_normalize_value():
    from pipelines.quotes.normalizer import QuoteNormalizer

    normalizer = QuoteNormalizer()
    normalized = normalizer.normalize_value(75_000_000_000)
    assert normalized == 75.0


def test_quote_normalize_record():
    from pipelines.quotes.normalizer import QuoteNormalizer

    normalizer = QuoteNormalizer()
    record = {"price_close": 15000, "volume": 5000000, "value": 75_000_000_000}
    normalized = normalizer.normalize(record)
    assert normalized["price_close"] == 15000.0
    assert normalized["volume"] == 5.0
    assert normalized["value"] == 75.0


def test_quote_normalize_batch():
    from pipelines.quotes.normalizer import QuoteNormalizer

    normalizer = QuoteNormalizer()
    records = [
        {"price_close": 15000, "volume": 5000000, "value": 75_000_000_000},
        {"price_close": 20000, "volume": 3000000, "value": 60_000_000_000},
    ]
    normalized = normalizer.normalize_batch(records)
    assert len(normalized) == 2

