from __future__ import annotations

from typing import Any

from core.ids import new_id
from core.logging import get_logger

logger = get_logger(__name__)

QUOTE_FIELD_MAP = {
    "close": "price_close",
    "open": "price_open",
    "high": "price_high",
    "low": "price_low",
    "last": "price_last",
    "change": "price_change",
    "change_pct": "price_change_pct",
    "vol": "volume",
    "val": "value",
    "trades": "trade_count",
    "yesterday": "price_yesterday",
    "first": "price_first",
    "max": "price_max",
    "min": "price_min",
    "ask_p": "ask_price",
    "ask_v": "ask_volume",
    "bid_p": "bid_price",
    "bid_v": "bid_volume",
}

TRADE_FIELD_MAP = {
    "nTran": "trade_id",
    "hEven": "time",
    "qTitTr": "quantity",
    "pTran": "price",
    "xqVarPJDrworP": "buyer_ref",
    "xqVarM1DrworP": "seller_ref",
    "canceled": "is_cancelled",
}

ORDERBOOK_FIELD_MAP = {
    "zOrdMeDem1": "bid_price_1",
    "qOrdMeDem1": "bid_volume_1",
    "pOrdMeDem1": "ask_price_1",
    "qOrdMeOf1": "ask_volume_1",
    "zOrdMeDem2": "bid_price_2",
    "qOrdMeDem2": "bid_volume_2",
    "pOrdMeOf2": "ask_price_2",
    "qOrdMeOf2": "ask_volume_2",
    "zOrdMeDem3": "bid_price_3",
    "qOrdMeDem3": "bid_volume_3",
    "pOrdMeOf3": "ask_price_3",
    "qOrdMeOf3": "ask_volume_3",
    "zOrdMeDem4": "bid_price_4",
    "qOrdMeDem4": "bid_volume_4",
    "pOrdMeOf4": "ask_price_4",
    "qOrdMeOf4": "ask_volume_4",
    "zOrdMeDem5": "bid_price_5",
    "qOrdMeDem5": "bid_volume_5",
    "pOrdMeOf5": "ask_price_5",
    "qOrdMeOf5": "ask_volume_5",
}


class QuoteHarmonizer:
    def harmonize(self, raw: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {"id": new_id("q")}
        for raw_key, value in raw.items():
            key = QUOTE_FIELD_MAP.get(raw_key, raw_key)
            normalized[key] = value
        if "instrument_id" not in normalized and "symbol" in normalized:
            normalized["instrument_id"] = normalized.get("symbol", "")
        normalized.setdefault("source", "tsetmc")
        normalized.setdefault("extra", {})
        logger.debug("Harmonized quote for %s", normalized.get("instrument_id", "?"))
        return normalized


class TradeHarmonizer:
    def harmonize(self, raw: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {"id": new_id("trade")}
        for raw_key, value in raw.items():
            key = TRADE_FIELD_MAP.get(raw_key, raw_key)
            normalized[key] = value
        if "is_cancelled" not in normalized:
            normalized["is_cancelled"] = False
        normalized.setdefault("source", "tsetmc")
        normalized.setdefault("extra", {})
        return normalized


class OrderBookHarmonizer:
    def harmonize(self, raw: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {"id": new_id("ob")}
        for raw_key, value in raw.items():
            key = ORDERBOOK_FIELD_MAP.get(raw_key, raw_key)
            normalized[key] = value
        normalized.setdefault("source", "tsetmc")
        normalized.setdefault("extra", {})
        return normalized
