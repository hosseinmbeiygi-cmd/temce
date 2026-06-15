from __future__ import annotations

from typing import Any

from core.constants import MarketType
from core.logging import get_logger

logger = get_logger(__name__)


MARKET_KEYWORDS = {
    MarketType.BOURS: ["بورس", "bourse", "bours"],
    MarketType.FARABOURS: ["فرابورس", "farabourse", "farabours"],
    MarketType.PAYEH: ["پایه", "payeh"],
    MarketType.OPTION: ["اختیار", "option", "opt"],
    MarketType.FUTURES: ["آتی", "futures"],
    MarketType.ETF: ["etf", "صندوق"],
}


SECTOR_MAP = {
    "financial": ["بانک", "بانکداری", "موسسه", "لیزینگ", "سرمایه", "بیمه"],
    "petrochemical": ["پتروشیمی", "شیمی", "پالایش"],
    "metal": ["فولاد", "مس", "آلومینیوم", "روی", "سرب", "فلز"],
    "pharmaceutical": ["دارو", "دارویی"],
    "automotive": ["خودرو", "خودروسازی", "ساخت"],
    "construction": ["سیمان", "ساختمان", "عمران"],
    "food": ["غذا", "غذایی", "کشاورزی"],
    "insurance": ["بیمه"],
    "holding": ["هلدینگ", "سرمایه گذاری"],
}


class MarketClassifier:
    def classify_market(self, data: dict[str, Any]) -> MarketType:
        symbol = (data.get("symbol") or "").upper()
        name = (data.get("name") or "").upper()
        market_str = (data.get("market") or "").lower()

        for market_type, keywords in MARKET_KEYWORDS.items():
            if any(kw.lower() in market_str for kw in keywords):
                return market_type
            if any(kw.upper() in symbol or kw.upper() in name for kw in keywords):
                return market_type
        return MarketType.BOURS

    def classify_sector(self, data: dict[str, Any]) -> str:
        group = (data.get("group") or data.get("sector") or "").lower()
        name = (data.get("name") or "").upper()
        symbol = (data.get("symbol") or "").upper()

        for sector, keywords in SECTOR_MAP.items():
            if group.startswith(tuple(kw.lower()[:3] for kw in keywords)):
                return sector
            if any(kw.upper() in name or kw.upper() in symbol for kw in keywords):
                return sector
        return "other"
