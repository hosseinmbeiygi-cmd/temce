from __future__ import annotations


def test_manual_provider_submit_quote():
    from providers.manual import ManualProvider

    provider = ManualProvider()
    result = provider.submit_quote(symbol="فولاد", payload={"price_close": 15000, "volume": 5000000})
    assert result is not None


def test_manual_provider_submit_trade():
    from providers.manual import ManualProvider

    provider = ManualProvider()
    result = provider.submit_trade(symbol="فولاد", payload={"price": 15050, "volume": 1000})
    assert result is not None


def test_manual_provider_validate():
    from providers.manual import ManualProvider

    provider = ManualProvider()
    assert provider.validate({"symbol": "فولاد", "price_close": 15000}) is True
    assert provider.validate({"price_close": 15000}) is False


def test_manual_provider_batch_submit():
    from providers.manual import ManualProvider

    provider = ManualProvider()
    items = [
        {"symbol": "فولاد", "price_close": 15000},
        {"symbol": "فملی", "price_close": 25000},
    ]
    results = provider.batch_submit(items, data_type="quote")
    assert len(results) == 2


def test_manual_provider_list_submissions():
    from providers.manual import ManualProvider

    provider = ManualProvider()
    submissions = provider.list_submissions()
    assert isinstance(submissions, list)
