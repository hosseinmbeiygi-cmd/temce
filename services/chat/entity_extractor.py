"""EntityExtractor — Extract entities from Persian/English text (Level 7 Slot Filling).

Extracts:
- Stock symbols (Persian & English)
- Numbers (prices, volumes, percentages)
- Filter conditions (RSI>30, P/E<8)
- Alert conditions (above/below thresholds)
- Date ranges
- Comparison targets
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

# Popular Iranian stock symbols for detection
KNOWN_SYMBOLS = [
    "فولاد", "فملی", "شپنا", "وبملت", "خودرو", "کگل", "شتران",
    "وغدیر", "تاپیکو", "کچاد", "پترول", "مس", "پارس", "حفاری",
    "شبندر", "بوعلی", "شاراک", "دکوثر", "رمپنا", "خساپا",
    "وآوا", "واعتبار", "وبانک", "وتجارت", "ونوین", "وبصادر",
    "وشهر", "فخوز", "فجر", "فایرا", "فاذر", "کاوه", "کرماشا",
    "قشیر", "قصفها", "قلرست", "قاروم", "غکورش", "غپاک",
    "شیران", "شاوان", "شسپا", "شگویا", "شبریز", "شصدف",
    "دسبد", "دشیری", "دماوند", "پارس", "پارسیان", "پیزد",
    "پکرمان", "پکویر", "پلاسک", "پتروشیمی", "پالایش",
    "نوری", "نیشکر", "نوین", "نفت", "نیرو", "وملی",
    "ومعادن", "ومپنا", "وبرق", "وبشهر", "وبهمن",
    "سپیدار", "سآب", "سخاش", "سپرمی", "سصفها", "سقاین",
    "تایرا", "تپکو", "تلیسه", "تنوین", "توسن",
    "های وب", "های وب", "همراه", "همراه اول",
    "فلات", "فلت", "فولای", "فپنتا", "فگستر",
    "کلر", "کلوند", "کمنگنز", "کماسه",
    "قرن", "قزوین", "قشکر", "قشهد",
    "گشان", "گکوثر", "گکیش", "گنگین", "گوهران",
    "مارون", "مادیرا", "میدکو", "ملت",
    "آکنتور", "آکنتور", "آریا", "آسامید",
    "چدن", "چکارن", "چنوپا",
    "لبوتان", "لخزر", "لطیف", "لکما",
    "فنابا", "فنرس", "فنرژی", "فنوع",
]

# Common Persian stopwords to exclude from symbol detection
PERSIAN_STOPWORDS = {
    "با", "به", "برای", "از", "در", "و", "که", "این", "آن",
    "را", "است", "هست", "هستند", "باشد", "می‌شود", "شود",
    "باید", "حتما", "اگر", "اما", "ولی", "یا", "نه",
    "یک", "دو", "سه", "چهار", "پنج", "اول", "آخر",
    "خواهد", "کرد", "کن", "کند", "کنید", "می‌کنم",
    "بود", "هستیم", "هستم", "دارد", "دارم", "دارند",
    "بگو", "بده", "بدهید", "بگیر", "بگیرید",
    "لطفا", "لطفاً", "ممنون", "تشکر",
    "نماد", "سهم", "سهام", "قیمت", "بازار", "بورس",
    "ها", "های", "هایی", "تر", "ترین",
    "هم", "خیلی", "بسیار", "چند", "چه", "چطور", "چرا",
    "حال", "حالا", "الان", "امروز", "دیروز", "فردا",
    "نیز", "همچنین", "البته", "مثلا", "مثلاً",
    "خوب", "بد", "عالی", "ضعیف", "قوی",
    "تحلیل", "بررسی", "وضعیت", "مقایسه",
}


class EntityExtractor:
    """Extract entities from conversational Persian/English text."""

    def __init__(self):
        self._symbol_cache: list[str] = KNOWN_SYMBOLS.copy()

    def extract(self, text: str) -> dict[str, Any]:
        """Extract all entities from text.

        Returns dict with:
        - symbols: list of detected stock symbols
        - numbers: list of extracted numbers
        - price: price value if detected
        - quantity: quantity if detected
        - conditions: filter conditions (field, operator, value)
        - alert_condition: alert condition
        - comparison_targets: symbols for comparison
        - date_range: extracted date range
        - intent_modifiers: additional intent hints
        """
        entities: dict[str, Any] = {
            "symbols": [],
            "numbers": [],
            "price": None,
            "quantity": None,
            "conditions": [],
            "alert_condition": None,
            "comparison_targets": [],
            "date_range": None,
            "intent_modifiers": [],
            "raw_text": text,
        }

        # 1. Extract symbols
        entities["symbols"] = self._extract_symbols(text)
        entities["comparison_targets"] = self._extract_comparison_targets(text)

        # 2. Extract numbers
        entities["numbers"] = self._extract_numbers(text)

        # 3. Extract price and quantity
        price_match = re.search(r"(قیمت|price|به[\s]*قیمت|با[\s]*قیمت|at)\s*(\d[\d,.]*)", text, re.IGNORECASE)
        if price_match:
            entities["price"] = self._clean_number(price_match.group(2))

        qty_match = re.search(r"(\d[\d,.]*)\s*(سهم|sahm|واحد|unit|عدد|عددی)", text)
        if qty_match:
            entities["quantity"] = self._clean_number(qty_match.group(1))

        # Also detect quantity before symbol
        qty_before = re.search(r"(\d+)\s*(فولاد|فملی|خودرو|شپنا|کگل|شتران|وبملت)", text)
        if qty_before and not entities["quantity"]:
            entities["quantity"] = int(qty_before.group(1))

        # 4. Extract filter conditions
        entities["conditions"] = self._extract_conditions(text)

        # 5. Extract alert conditions
        alert_match = re.search(
            r"هشدار\s*(\S+)\s*(rsi|price|قیمت|حجم|volume)\s*(above|below|بالاتر|پایین‌تر)\s*(\d+)",
            text, re.IGNORECASE
        )
        if alert_match:
            entities["alert_condition"] = {
                "symbol": alert_match.group(1),
                "field": "rsi" if "rsi" in alert_match.group(2).lower() else "price",
                "operator": "above" if alert_match.group(3).lower() in ("above", "بالاتر") else "below",
                "threshold": float(alert_match.group(4)),
            }

        # 6. Extract date range
        entities["date_range"] = self._extract_date_range(text)

        # 7. Extract intent modifiers
        entities["intent_modifiers"] = self._extract_intent_modifiers(text)

        return entities

    def _extract_symbols(self, text: str) -> list[str]:
        """Extract stock symbols from text with Unicode normalization."""
        found = []
        text_clean = text.strip()

        # Normalize Unicode to handle different forms of Persian chars
        # (e.g., ي vs ی, ك vs ک)
        text_normalized = unicodedata.normalize('NFKC', text_clean)

        # Sort symbols by length (longest first) to match more specific names
        sorted_symbols = sorted(self._symbol_cache, key=len, reverse=True)
        for sym in sorted_symbols:
            sym_normalized = unicodedata.normalize('NFKC', sym)
            if (sym in text_clean or sym_normalized in text_normalized) and sym not in found:
                found.append(sym)

        return found

    def _extract_comparison_targets(self, text: str) -> list[str]:
        """Extract symbols specifically for comparison."""
        targets = []
        compare_patterns = [
            r"مقایسه\s*(\S+)\s*(و|با)\s*(\S+)",
            r"(\S+)\s*(مقایسه|با)\s*(\S+)",
            r"(کدوم\s*بهتره)\s*(\S+)\s*(و|با)\s*(\S+)",
        ]

        for pattern in compare_patterns:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                for g in groups:
                    if g and g not in ("و", "با", "مقایسه", "کدوم بهتره") and \
                       g not in PERSIAN_STOPWORDS and len(g) >= 2:
                        targets.append(g)
                break  # Use first matching pattern

        return targets

    def _extract_numbers(self, text: str) -> list[float]:
        """Extract all numbers from text."""
        numbers = []
        for match in re.finditer(r"(\d[\d,.]*)", text):
            num = self._clean_number(match.group(1))
            if num is not None:
                numbers.append(num)
        return numbers

    def _extract_conditions(self, text: str) -> list[dict[str, Any]]:
        """Extract filter conditions."""
        conditions = []

        # Pattern: FIELD OPERATOR VALUE
        field_patterns = {
            "rsi": r"RSI\s*(<=|>=|<|>|=)\s*(\d+(?:\.\d+)?)",
            "pe": r"P/E\s*(<=|>=|<|>|=)\s*(\d+(?:\.\d+)?)",
            "roe": r"ROE\s*(<=|>=|<|>|=)\s*(\d+(?:\.\d+)?)",
            "smc": r"SMC\s*(<=|>=|<|>|=)\s*(0?\.\d+|\d+(?:\.\d+)?)",
            "volume": r"(حجم|volume|V)\s*(<=|>=|<|>|=)\s*(\d+)",
            "price": r"(قیمت|price|P)\s*(<=|>=|<|>|=)\s*(\d+)",
            "change_pct": r"(بازده|change|C|تغییر)\s*(<=|>=|<|>|=)\s*(-?\d+(?:\.\d+)?)",
            "liquidity": r"(نقدشوندگی|liquidity|LQ)\s*(<=|>=|<|>|=)\s*(0?\.\d+|\d+(?:\.\d+)?)",
            "power": r"(قدرت|power|PW)\s*(<=|>=|<|>|=)\s*(0?\.\d+|\d+(?:\.\d+)?)",
            "accumulation": r"(تجمع|ACC|acc)\s*(<=|>=|<|>|=)\s*(0?\.\d+|\d+(?:\.\d+)?)",
            "absorption": r"(جذب|ABS|abs)\s*(<=|>=|<|>|=)\s*(0?\.\d+|\d+(?:\.\d+)?)",
        }

        for field, pattern in field_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                operator_map = {
                    ">": "gt", ">=": "gte",
                    "<": "lt", "<=": "lte",
                    "=": "eq",
                }
                conditions.append({
                    "field": field,
                    "operator": operator_map.get(match.group(1), "eq"),
                    "value": float(match.group(2)),
                })

        # Also extract natural language conditions
        natural_patterns = [
            (r"RSI\s*(پایین|زیر|کمتر)\s*از\s*(\d+)", "rsi", "lt"),
            (r"RSI\s*(بالا|بالاتر|بیشتر)\s*از\s*(\d+)", "rsi", "gt"),
            (r"P/E\s*(پایین|زیر|کمتر)\s*از\s*(\d+)", "pe", "lt"),
            (r"ROE\s*(بالا|بالاتر|بیشتر)\s*از\s*(\d+)", "roe", "gt"),
        ]

        for pattern, field, operator in natural_patterns:
            match = re.search(pattern, text)
            if match:
                conditions.append({
                    "field": field,
                    "operator": operator,
                    "value": float(match.group(2)),
                })

        return conditions

    def _extract_date_range(self, text: str) -> dict[str, str] | None:
        """Extract date range from text."""
        # Persian date patterns
        patterns = [
            r"از\s*(\d{4}/\d{2}/\d{2})\s*(تا|الی)\s*(\d{4}/\d{2}/\d{2})",
            r"از\s*(\d{4}-\d{2}-\d{2})\s*(تا|الی)\s*(\d{4}-\d{2}-\d{2})",
            r"بین\s*(\d{4}/\d{2}/\d{2})\s*(تا|و|الی)\s*(\d{4}/\d{2}/\d{2})",
            r"(\d{1,2})\s*(روز|ماه|سال)\s*(اخیر|گذشته|قبل|پیش)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                if len(match.groups()) == 3 and match.group(2) in ("تا", "الی", "و"):
                    return {
                        "start": match.group(1),
                        "end": match.group(3),
                    }
                elif len(match.groups()) == 3 and match.group(3) in ("اخیر", "گذشته", "قبل", "پیش"):
                    amount = int(match.group(1))
                    unit = match.group(2)
                    return {
                        "relative_amount": amount,
                        "relative_unit": unit,
                    }

        return None

    def _extract_intent_modifiers(self, text: str) -> list[str]:
        """Extract intent modifiers (urgency, detail level, etc.)."""
        modifiers = []

        # Urgency
        if re.search(r"(فوری|فورا|سریع|زود|عجله)", text):
            modifiers.append("urgent")

        # Detail level
        if re.search(r"(کامل|جامع|جزئیات|مفصل|detailed|comprehensive)", text):
            modifiers.append("detailed")
        elif re.search(r"(خلاصه|مختصر|summary|brief|short)", text):
            modifiers.append("brief")

        # Format
        if re.search(r"(جدول|table|لیست|list)", text):
            modifiers.append("tabular")
        if re.search(r"(نمودار|chart|graph)", text):
            modifiers.append("chart")

        # Time period
        if re.search(r"(امروز|today)", text):
            modifiers.append("today")
        if re.search(r"(هفته|week)", text):
            modifiers.append("weekly")
        if re.search(r"(ماه|ماهیانه|month)", text):
            modifiers.append("monthly")
        if re.search(r"(سال|year|سالیانه)", text):
            modifiers.append("yearly")

        return modifiers

    @staticmethod
    def _clean_number(text_num: str) -> float | None:
        """Clean a number string and convert to float."""
        try:
            cleaned = text_num.replace(",", "").replace("٬", "")
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    def update_symbols(self, symbols: list[str]) -> None:
        """Update known symbols list (e.g., from database)."""
        new_symbols = [s for s in symbols if s not in self._symbol_cache]
        self._symbol_cache.extend(new_symbols)
        logger.info("EntityExtractor: added %d new symbols", len(new_symbols))


# Convenience instance
_default_extractor = EntityExtractor()


def extract_entities(text: str) -> dict[str, Any]:
    """Quick-access function to extract entities from text."""
    return _default_extractor.extract(text)
