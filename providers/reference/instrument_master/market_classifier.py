from __future__ import annotations

from typing import Any

from core.constants import MarketType
from core.logging import get_logger

logger = get_logger(__name__)


# New venues come first: their labels ("بورس کالا", "بورس ارز") contain the
# generic "بورس" token, so they must win before the BOURS entry is reached.
MARKET_KEYWORDS: dict[MarketType, list[str]] = {
    MarketType.SUKUK: ["صکوک", "sukuk", "اوراق بدهی", "fixed income", "اخزا"],
    MarketType.FX: ["بورس ارز", "irfx", "currency market", "fx market"],
    MarketType.COMMODITY: ["بورس کالا", "ime", "commodity exchange"],
    MarketType.BOURS: ["بورس", "bourse", "bours"],
    MarketType.FARABOURS: ["فرابورس", "farabourse", "farabours"],
    MarketType.PAYEH: ["پایه", "payeh"],
    MarketType.OPTION: ["اختیار", "option", "opt"],
    MarketType.FUTURES: ["آتی", "futures"],
    MarketType.ETF: ["etf", "صندوق"],
}

# Symbol/name evidence is kept separate and deliberately narrow for the new
# markets so an equity whose name merely contains a commodity word is not
# reclassified as an IME contract.
NAME_KEYWORDS: dict[MarketType, list[str]] = {
    MarketType.SUKUK: ["صکوک", "اخزا"],
    MarketType.FX: [],
    MarketType.COMMODITY: ["گندم", "ذرت", "کنجاله", "زعفران", "پسته", "زیره", "سکه"],
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
            name_keywords = NAME_KEYWORDS.get(market_type, [])
            if any(kw.upper() in symbol or kw.upper() in name for kw in name_keywords):
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
