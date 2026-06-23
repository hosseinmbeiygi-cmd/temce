from __future__ import annotations


def test_tsetmc_parse_quote():
    from providers.tsetmc.parser import TsetmcParser

    parser = TsetmcParser()
    raw = {"PriceChange": 100, "PriceChangePercent": 0.67, "ClosingPrice": 15000}
    quote = parser.parse_quote(raw)
    assert quote is not None


def test_tsetmc_parse_trade():
    from providers.tsetmc.parser import TsetmcParser

    parser = TsetmcParser()
    raw = {"Price": 15050, "Quantity": 1000, "DateTime": "20240115123005"}
    trade = parser.parse_trade(raw)
    assert trade is not None


def test_tsetmc_parse_orderbook():
    from providers.tsetmc.parser import TsetmcParser

    parser = TsetmcParser()
    raw = {
        "BidPrices": [15040, 15030],
        "BidVolumes": [15000, 22000],
        "AskPrices": [15060, 15070],
        "AskVolumes": [10000, 25000],
    }
    orderbook = parser.parse_orderbook(raw)
    assert orderbook is not None
    assert len(orderbook["bids"]) == 2


def test_tsetmc_parse_instrument():
    from providers.tsetmc.parser import TsetmcParser

    parser = TsetmcParser()
    raw = {"Symbol": "فولاد", "Name": "فولاد مبارکه", "ISIN": "IRO1FOLD0001"}
    instrument = parser.parse_instrument(raw)
    assert instrument is not None


def test_tsetmc_normalize_symbol():
    from providers.tsetmc.parser import TsetmcParser

    parser = TsetmcParser()
    assert parser.normalize_symbol("فولاد") == "فولاد"

