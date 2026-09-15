"""Normalizer base — فاز 2-1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class NormalizedRecord:
    symbol: str
    isin: str | None
    market: str
    asset_class: str
    strike: float | None = None
    expiry: str | None = None
    price: float | None = None
    volume: int | None = None
    raw_store_id: int | None = None


class BaseNormalizer:
    def normalize(self, raw: dict[str, Any], raw_store_id: int | None = None) -> NormalizedRecord:
        # نگاشت مشترک — هر Adapter override می‌کند
        return NormalizedRecord(
            symbol=raw.get("symbol") or raw.get("l18") or "",
            isin=raw.get("isin"),
            market=raw.get("market") or "IME",
            asset_class=raw.get("asset_class") or "equity",
            raw_store_id=raw_store_id,
        )
