from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from core.logging import get_logger

from . import ParsedEvent, Parser

logger = get_logger(__name__)


class TsetmcMarketWatchParser(Parser):
    def source_name(self) -> str:
        return "tsetmc_marketwatch"

    def can_parse(self, source: str, endpoint: str, content_type: str) -> bool:
        return source == "tsetmc_marketwatch"

    async def parse(self, payload: bytes) -> list[ParsedEvent]:
        data = json.loads(payload)
        events: list[ParsedEvent] = []
        now = datetime.now(UTC).isoformat()

        records = data if isinstance(data, list) else data.get("marketData", [])
        for rec in records:
            events.append(
                ParsedEvent(
                    source="tsetmc_marketwatch",
                    event_type="market_snapshot",
                    data=self._extract_snapshot(rec),
                    raw_object_key="",
                    fetch_time=now,
                    parsed_at=now,
                )
            )
        return events

    @staticmethod
    def _extract_snapshot(rec: dict[str, Any]) -> dict[str, Any]:
        return {
            "instrument_id": rec.get("insCode"),
            "symbol": rec.get("lVal18AFC"),
            "name": rec.get("lVal30"),
            "last_price": _to_decimal(rec.get("pDrCotVal")),
            "close_price": _to_decimal(rec.get("pClosing")),
            "first_price": _to_decimal(rec.get("priceFirst")),
            "high_price": _to_decimal(rec.get("priceMax")),
            "low_price": _to_decimal(rec.get("priceMin")),
            "volume": int(rec.get("qTotTran5J", 0)),
            "value": _to_decimal(rec.get("valTran")),
            "trade_count": int(rec.get("numberOfTrades", 0)),
            "yesterday_close": _to_decimal(rec.get("yesterdayPrice")),
            "eps": _to_decimal(rec.get("eps")),
            "base_volume": int(rec.get("baseVol", 0)),
        }


class TsetmcTradeParser(Parser):
    def source_name(self) -> str:
        return "tsetmc_trades"

    def can_parse(self, source: str, endpoint: str, content_type: str) -> bool:
        return source == "tsetmc_trades"

    async def parse(self, payload: bytes) -> list[ParsedEvent]:
        data = json.loads(payload)
        events: list[ParsedEvent] = []
        now = datetime.now(UTC).isoformat()

        records = data if isinstance(data, list) else data.get("closingPriceData", [])
        for rec in records:
            events.append(
                ParsedEvent(
                    source="tsetmc_trades",
                    event_type="trade_tick",
                    data=self._extract_trade(rec),
                    raw_object_key="",
                    fetch_time=now,
                    parsed_at=now,
                )
            )
        return events

    @staticmethod
    def _extract_trade(rec: dict[str, Any]) -> dict[str, Any]:
        return {
            "instrument_id": rec.get("insCode"),
            "trade_date": rec.get("dEven"),
            "price": _to_decimal(rec.get("pClosing")),
            "volume": int(rec.get("qTotTran5J", 0)),
            "value": _to_decimal(rec.get("valTran")),
            "trade_count": int(rec.get("numberOfTrades", 0)),
            "last_price": _to_decimal(rec.get("pDrCotVal")),
            "first_price": _to_decimal(rec.get("priceFirst")),
            "high_price": _to_decimal(rec.get("priceMax")),
            "low_price": _to_decimal(rec.get("priceMin")),
        }


class TsetmcOrderBookParser(Parser):
    def source_name(self) -> str:
        return "tsetmc_orderbook"

    def can_parse(self, source: str, endpoint: str, content_type: str) -> bool:
        return source == "tsetmc_orderbook"

    async def parse(self, payload: bytes) -> list[ParsedEvent]:
        data = json.loads(payload)
        events: list[ParsedEvent] = []
        now = datetime.now(UTC).isoformat()

        bids = data.get("buyRows", []) or data.get("buy", [])
        asks = data.get("sellRows", []) or data.get("sell", [])
        ins_code = data.get("insCode")

        for rank, level in enumerate(bids):
            events.append(
                ParsedEvent(
                    source="tsetmc_orderbook",
                    event_type="orderbook_level",
                    data={
                        "instrument_id": ins_code,
                        "side": "bid",
                        "price": _to_decimal(level.get("pPrice")),
                        "volume": int(level.get("qTit", 0)),
                        "order_count": int(level.get("zOrder", 0)),
                        "rank": rank + 1,
                    },
                    raw_object_key="",
                    fetch_time=now,
                    parsed_at=now,
                )
            )
        for rank, level in enumerate(asks):
            events.append(
                ParsedEvent(
                    source="tsetmc_orderbook",
                    event_type="orderbook_level",
                    data={
                        "instrument_id": ins_code,
                        "side": "ask",
                        "price": _to_decimal(level.get("pPrice")),
                        "volume": int(level.get("qTit", 0)),
                        "order_count": int(level.get("zOrder", 0)),
                        "rank": rank + 1,
                    },
                    raw_object_key="",
                    fetch_time=now,
                    parsed_at=now,
                )
            )
        return events


def _to_decimal(val: Any) -> str | None:
    if val is None:
        return None
    try:
        return str(Decimal(str(val)))
    except Exception:
        return None
