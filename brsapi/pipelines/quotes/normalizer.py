from __future__ import annotations

from typing import Any


class QuoteNormalizer:
    """Normalizer for quote data."""

    def normalize_price(self, price: float) -> float:
        return float(price)

    def normalize_volume(self, volume: int) -> float:
        return volume / 1_000_000.0

    def normalize_value(self, value: float) -> float:
        return value / 1_000_000_000.0

    def normalize(self, record: dict[str, Any]) -> dict[str, Any]:
        result = dict(record)
        if "price_close" in result:
            result["price_close"] = self.normalize_price(result["price_close"])
        if "volume" in result:
            result["volume"] = self.normalize_volume(result["volume"])
        if "value" in result:
            result["value"] = self.normalize_value(result["value"])
        return result

    def normalize_batch(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.normalize(r) for r in records]
