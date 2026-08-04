from __future__ import annotations

import json

from ingestion.parser.tsetmc_parsers import (
    TsetmcMarketWatchParser,
    TsetmcOrderBookParser,
    TsetmcTradeParser,
)


class TestTsetmcMarketWatchParser:
    def test_can_parse_marketwatch(self) -> None:
        parser = TsetmcMarketWatchParser()
        assert parser.can_parse("tsetmc_marketwatch", "/MarketData/MarketData", "application/json") is True
        assert parser.can_parse("tsetmc_trades", "", "") is False

    async def test_parse_empty_list(self) -> None:
        parser = TsetmcMarketWatchParser()
        events = await parser.parse(json.dumps([]).encode())
        assert events == []

    async def test_parse_single_record(self) -> None:
        payload = json.dumps(
            [
                {
                    "insCode": "123",
                    "lVal18AFC": "فولاد",
                    "pDrCotVal": "50000",
                    "qTotTran5J": "1000",
                }
            ]
        ).encode()
        parser = TsetmcMarketWatchParser()
        events = await parser.parse(payload)
        assert len(events) == 1
        assert events[0].source == "tsetmc_marketwatch"
        assert events[0].event_type == "market_snapshot"
        assert events[0].data["instrument_id"] == "123"
        assert events[0].data["symbol"] == "فولاد"
        assert events[0].data["volume"] == 1000


class TestTsetmcTradeParser:
    async def test_parse_trades(self) -> None:
        payload = json.dumps(
            {
                "closingPriceData": [{"insCode": "123", "pClosing": "15000", "qTotTran5J": "500"}],
            }
        ).encode()
        parser = TsetmcTradeParser()
        events = await parser.parse(payload)
        assert len(events) == 1
        assert events[0].event_type == "trade_tick"
        assert events[0].data["instrument_id"] == "123"

    async def test_parse_empty(self) -> None:
        parser = TsetmcTradeParser()
        events = await parser.parse(json.dumps({}).encode())
        assert events == []


class TestTsetmcOrderBookParser:
    async def test_parse_orderbook(self) -> None:
        payload = json.dumps(
            {
                "insCode": "123",
                "buyRows": [{"pPrice": "100", "qTit": "10", "zOrder": "3", "xOrder": "1"}],
                "sellRows": [{"pPrice": "101", "qTit": "5", "zOrder": "2", "xOrder": "1"}],
            }
        ).encode()
        parser = TsetmcOrderBookParser()
        events = await parser.parse(payload)
        assert len(events) == 2
        assert events[0].data["side"] == "bid"
        assert events[1].data["side"] == "ask"

    async def test_parse_empty(self) -> None:
        parser = TsetmcOrderBookParser()
        events = await parser.parse(json.dumps({}).encode())
        assert events == []
