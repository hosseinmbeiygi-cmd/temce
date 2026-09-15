"""CompoundSplitter — Split compound/mixed queries into sub-queries (Level 9).

Handles patterns like:
- "تحلیل فولاد و مقایسه با شپنا" → ["تحلیل فولاد", "مقایسه فولاد با شپنا"]
- "قیمت فولاد چقدره و اخبارش رو بده" → ["قیمت فولاد", "اخبار فولاد"]
- "فولاد رو تحلیل کن و بهترین سهم‌ها رو بگو" → ["تحلیل فولاد", "بهترین سهم‌ها"]
"""

from __future__ import annotations

import re


class CompoundSplitter:
    """Detect and split compound (mixed) queries into sub-queries."""

    # Connectors that join two independent sub-queries
    CONNECTORS = [
        r"\s+و\s+",
        r"\s+و\s+هم\s+",
        r"\s+و\s+نیز\s+",
        r"\s+و\s+بعد\s+",
        r"\s+سپس\s+",
        r"\s+بعدش\s+",
        r"\s+همچنین\s+",
        r"\s+علاوه بر\s+",
        r"\s+and\s+",
        r"\s+then\s+",
        r"\s+also\s+",
        r"\s*,+\s*و\s*",
        r"\s*[،,]\s*",
    ]

    # Actions that can chain: "X رو تحلیل کن و Y رو مقایسه کن"
    ACTION_PATTERNS = [
        r"(تحلیل|بررسی|وضعیت)\s*(\S+)\s*(رو|را)?\s*(و)?",
        r"(قیمت|نمودار|اخبار)\s*(\S+)\s*(رو|را)?\s*(و)?",
        r"(مقایسه)\s*(\S+)\s*(و|با)\s*(\S+)\s*(رو|را)?\s*(و)?",
    ]

    @classmethod
    def is_compound(cls, text: str) -> bool:
        """Check if text contains compound queries."""
        # Check for multiple connectors
        connector_count = 0
        for conn in cls.CONNECTORS:
            matches = re.findall(conn, text)
            connector_count += len(matches)

        # Check for multiple actions
        action_count = 0
        for pattern in cls.ACTION_PATTERNS:
            matches = re.findall(pattern, text)
            action_count += len(matches)

        # Also check for multiple intents
        # e.g., "فولاد" appears once but intent switches
        if cls._count_potential_intents(text) >= 2:
            return True

        return connector_count >= 1 and action_count >= 1

    @classmethod
    def split(cls, text: str) -> list[str]:
        """Split compound text into independent sub-queries.

        Returns list of query strings, or [text] if not compound.
        """
        text = text.strip()
        if not text:
            return []

        # Try to split by connectors
        parts = cls._split_by_connectors(text)

        # If splitting didn't work, try to extract independent queries
        if len(parts) <= 1:
            parts = cls._extract_independent_queries(text)

        # Clean up parts
        cleaned = []
        for part in parts:
            part = part.strip().strip("،,.").strip()
            if part and len(part) >= 3:
                cleaned.append(part)

        return cleaned if len(cleaned) > 1 else [text]

    @classmethod
    def _split_by_connectors(cls, text: str) -> list[str]:
        """Split text by compound connectors."""
        # Build combined pattern
        conn_pattern = "|".join(cls.CONNECTORS)
        parts = re.split(conn_pattern, text)
        return [p.strip() for p in parts if p.strip()]

    @classmethod
    def _extract_independent_queries(cls, text: str) -> list[str]:
        """Extract independent sub-queries from text."""
        queries = []

        # Pattern: "X رو تحلیل کن و Y رو مقایسه کن"
        # Look for action-entity pairs
        actions = [
            ("تحلیل", r"تحلیل\s*(\S+)\s*(رو|را)?"),
            ("بررسی", r"بررسی\s*(\S+)\s*(رو|را)?"),
            ("قیمت", r"قیمت\s*(\S+)\s*(رو|را)?"),
            ("اخبار", r"اخبار\s*(\S+)\s*(رو|را)?"),
            ("نمودار", r"نمودار\s*(\S+)\s*(رو|را)?"),
        ]

        for action, pattern in actions:
            match = re.search(pattern, text)
            if match:
                symbol = match.group(1)
                if symbol and len(symbol) >= 2:
                    queries.append(f"{action} {symbol}")

        # Pattern: "مقایسه X و Y"
        compare_match = re.search(r"مقایسه\s*(\S+)\s*(و|با)\s*(\S+)", text)
        if compare_match:
            queries.append(f"مقایسه {compare_match.group(1)} و {compare_match.group(3)}")

        # Pattern: "بهترین سهم‌ها" + extra
        if "بهترین" in text and "تحلیل" not in queries:
            queries.append("بهترین سهم‌ها")

        # Pattern: "بازار" + extra
        if "بازار" in text:
            market_queries = [q for q in queries if "بازار" not in q]
            queries = market_queries + ["خلاصه بازار"]

        return queries

    @classmethod
    def _count_potential_intents(cls, text: str) -> int:
        """Count the number of potential intents in text."""
        intent_keywords = {
            "تحلیل": 1,
            "بررسی": 1,
            "وضعیت": 1,
            "قیمت": 1,
            "نمودار": 1,
            "اخبار": 1,
            "مقایسه": 1,
            "بهترین": 1,
            "بازار": 1,
            "فیلتر": 1,
            "غربال": 1,
            "پیش‌بینی": 1,
            "سیگنال": 1,
            "اضافه": 1,
            "حذف": 1,
            "دیده‌بان": 1,
            "هشدار": 1,
            "پرتفوی": 1,
            "سبد": 1,
            "بک‌تست": 1,
            "آموزش": 1,
            "طلا": 1,
            "دلار": 1,
            "سکه": 1,
            "گزارش": 1,
            "نقشه": 1,
        }

        count = 0
        for keyword, value in intent_keywords.items():
            if keyword in text:
                count += value

        return count


def split_compound(text: str) -> list[str]:
    """Convenience function to split compound text."""
    return CompoundSplitter.split(text)


def is_compound(text: str) -> bool:
    """Convenience function to check if text is compound."""
    return CompoundSplitter.is_compound(text)
