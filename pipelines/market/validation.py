from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result

logger = get_logger(__name__)

QUOTE_REQUIRED = ["instrument_id", "price_close"]
QUOTE_POSITIVE = ["price_close", "volume", "value"]
QUOTE_MAX_PRICE = 10_000_000
QUOTE_MAX_VOLUME = 100_000_000

TRADE_REQUIRED = ["instrument_id", "price", "quantity"]
TRADE_POSITIVE = ["price", "quantity"]

ORDERBOOK_REQUIRED = ["instrument_id"]
ORDERBOOK_POSITIVE_FIELDS = [
    "bid_price_1",
    "bid_volume_1",
    "ask_price_1",
    "ask_volume_1",
    "bid_price_2",
    "bid_volume_2",
    "ask_price_2",
    "ask_volume_2",
    "bid_price_3",
    "bid_volume_3",
    "ask_price_3",
    "ask_volume_3",
    "bid_price_4",
    "bid_volume_4",
    "ask_price_4",
    "ask_volume_4",
    "bid_price_5",
    "bid_volume_5",
    "ask_price_5",
    "ask_volume_5",
]


class MarketDataValidator:
    def validate_quote(self, data: dict[str, Any]) -> Result[dict[str, Any]]:
        for field in QUOTE_REQUIRED:
            if field not in data or data[field] is None:
                return Result.fail(f"Missing required field: {field}")
        for field in QUOTE_POSITIVE:
            val = data.get(field, 0)
            if isinstance(val, (int, float)) and val < 0:
                return Result.fail(f"Invalid negative {field}: {val}")
        price = data.get("price_close", 0)
        if isinstance(price, (int, float)) and price > QUOTE_MAX_PRICE:
            return Result.fail(f"Price exceeds maximum: {price}")
        volume = data.get("volume", 0)
        if isinstance(volume, (int, float)) and volume > QUOTE_MAX_VOLUME:
            return Result.fail(f"Volume exceeds maximum: {volume}")
        return Result.ok(data)

    def validate_trade(self, data: dict[str, Any]) -> Result[dict[str, Any]]:
        for field in TRADE_REQUIRED:
            if field not in data or data[field] is None:
                return Result.fail(f"Missing required field: {field}")
        for field in TRADE_POSITIVE:
            val = data.get(field, 0)
            if isinstance(val, (int, float)) and val < 0:
                return Result.fail(f"Invalid negative {field}: {val}")
        return Result.ok(data)

    def validate_orderbook(self, data: dict[str, Any]) -> Result[dict[str, Any]]:
        for field in ORDERBOOK_REQUIRED:
            if field not in data or data[field] is None:
                return Result.fail(f"Missing required field: {field}")
        for field in ORDERBOOK_POSITIVE_FIELDS:
            val = data.get(field, 0)
            if isinstance(val, (int, float)) and val < 0:
                return Result.fail(f"Invalid negative {field}: {val}")
        return Result.ok(data)

    def validate_batch(
        self, records: list[dict[str, Any]], record_type: str = "quote"
    ) -> tuple[list[dict[str, Any]], list[str]]:
        valid, errors = [], []
        validator = {
            "quote": self.validate_quote,
            "trade": self.validate_trade,
            "orderbook": self.validate_orderbook,
        }.get(record_type, self.validate_quote)
        for record in records:
            result = validator(record)
            if result.success:
                valid.append(record)
            else:
                errors.append(result.error or "validation failed")
        logger.info("Validated %d/%d %s records", len(valid), len(records), record_type)
        return valid, errors
