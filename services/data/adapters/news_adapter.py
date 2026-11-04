"""News regime normalizer (Assistant 4 source layer, phase 3).

Input : free text / feed item (raw string) plus source metadata.
Output: payload with ``labels`` drawn **only** from the fixed set
{ dollar, geopolitical, monetary_policy, coin_supply, other } and a
non-price ``note``.  This layer cleans text and forwards source metadata — it
does **not** invent monetary/political labels or policy stances (Assistant 1/3
own the labelling module; this adapter is the deterministic fallback).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .base import BaseAdapter, MarketRecord

FIXED_LABELS = ("dollar", "geopolitical", "monetary_policy", "coin_supply", "other")

_LABEL_KEYWORDS = {
    "dollar": ("دلار", "usd", "dollar", "نرخ ارز", "ارز"),
    "geopolitical": ("geopolitical", "تحریم", "جنگ", "جغرافیایی", "sanction"),
    "monetary_policy": ("بانک مرکزی", "نرخ بهره", "سود", "monetary_policy", "cbi"),
    "coin_supply": ("سکه", "نما", "mint", "coin_supply", "اینگوت"),
}

_BANNED_WORDS = ("هدف قیمت", "target price", "خرید", "فروش", "buy", "sell")


def _map_labels(text: str) -> list[str]:
    lowered = text.lower()
    hits = [
        label
        for label, keywords in _LABEL_KEYWORDS.items()
        if any(k.lower() in lowered for k in keywords)
    ]
    if not hits:
        return ["other"]
    return hits[:3]


def _clean_note(text: str) -> str:
    """Short non-price note: strip price-looking tokens and action language."""
    cleaned = re.sub(r"\d[\d,]*\s*(تومان|ریال|toman|rial|usd|\$)", " ", text, flags=re.I)
    for word in _BANNED_WORDS:
        cleaned = cleaned.replace(word, " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .،:")
    return cleaned[:200] if cleaned else "متن منبع بدون سگنال قیمتی"


class NewsAdapter(BaseAdapter):
    source = "news_normalize"

    def extract(self, raw: dict[str, Any]) -> dict[str, Any]:
        text = raw.get("text") or raw.get("body") or ""
        return {
            "symbol": None,
            "value": None,
            "unit": None,
            "asOf": raw.get("asOf"),
            "source": raw.get("source"),
            "quality": raw.get("quality") or "DELAYED",
            "labels": _map_labels(text),
            "note": _clean_note(text),
        }


def news_normalize(raw: dict[str, Any], now: datetime | None = None) -> MarketRecord:
    return NewsAdapter().normalize(raw, now=now)
