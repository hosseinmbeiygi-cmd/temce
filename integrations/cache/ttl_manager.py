from __future__ import annotations

from core.config import settings


class TTLManager:
    TTL_PRESETS: dict[str, int] = {
        "quote": settings.CACHE_TTL_QUOTE,
        "instrument": settings.CACHE_TTL_INSTRUMENT,
        "signal": 600,
        "recommendation": 900,
        "analysis": 1800,
        "market_overview": 60,
        "historical": 3600,
        "reference": 86400,
        "search": 300,
        "session": 1800,
        "user": 3600,
    }

    def get_ttl(self, key: str, category: str | None = None) -> int:
        if category and category in self.TTL_PRESETS:
            return self.TTL_PRESETS[category]
        for cat, ttl in self.TTL_PRESETS.items():
            if cat in key:
                return ttl
        return settings.redis_default_ttl

    def set_ttl(self, category: str, ttl: int) -> None:
        self.TTL_PRESETS[category] = ttl

    def get_all_presets(self) -> dict[str, int]:
        return dict(self.TTL_PRESETS)

    def refresh_before_expiry(self, key: str, category: str) -> bool:
        return False

    def category_for_key(self, key: str) -> str:
        for cat in self.TTL_PRESETS:
            if cat in key:
                return cat
        return "default"

    def compute_ttl(self, base_ttl: int, factor: float = 1.0) -> int:
        return max(1, int(base_ttl * factor))
