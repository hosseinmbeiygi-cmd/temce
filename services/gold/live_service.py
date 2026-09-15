"""Gold live prices service — بسته‌بندی BrsApi برای داشبورد طلا.

لایه انتزاع بین endpoint و BrsApi:
  • کش داخلی (3 ثانیه TTL) — در production با Redis جایگزین می‌شود
  • fallback: آخرین مقدار معتبر (stale) + پرچم is_stale
  • تلاش مجدد: 3 بار
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from brsapi.services.query_service import BrsApiQueryService
from core.logging import get_logger

logger = get_logger(__name__)

CACHE_TTL_SECONDS = 3
RETRY_COUNT = 3
RETRY_BACKOFF = 0.4

# نگاشت نام commodity در BrsApi به نام استاندارد داشبورد
GOLD_KEY_MAP = {
    "ounce": ("gold_oz_usd", "usd"),  # اونس طلا
    "18k": ("gold_18k_irr", "irr"),  # طلای ۱۸ عیار هر گرم
    "coin_bahar": ("coin_bahar_irr", "irr"),  # سکه بهار آزادی
    "usd": ("usd_irr", "irr"),  # دلار آزاد
}


@dataclass
class _Cache:
    data: dict[str, Any]
    timestamp: float


class GoldLiveService:
    """سرویس قیمت‌های زنده بازار طلا."""

    def __init__(self, brsapi: BrsApiQueryService) -> None:
        self.brsapi = brsapi
        self._cache: _Cache | None = None

    # ── Cache helpers ──────────────────────────────────────────

    def _is_fresh(self) -> bool:
        return self._cache is not None and (time.monotonic() - self._cache.timestamp) < CACHE_TTL_SECONDS

    def _set_cache(self, data: dict[str, Any]) -> None:
        self._cache = _Cache(data=data, timestamp=time.monotonic())

    # ── Public API ─────────────────────────────────────────────

    async def get_live_prices(self, force_refresh: bool = False) -> dict[str, Any]:
        """قیمت لحظه‌ای طلا، سکه و دلار. کش ۳ ثانیه."""
        if not force_refresh and self._is_fresh() and self._cache is not None:
            return {**self._cache.data, "is_stale": False}

        try:
            data = await self._fetch_with_retry()
        except Exception as exc:
            logger.exception("Failed to fetch gold live prices")
            if self._cache is not None:
                return {**self._cache.data, "is_stale": True}
            # cold start fail → empty shape so the API still returns 200
            return self._empty_shape(is_stale=True, error=str(exc))

        self._set_cache(data)
        return {**data, "is_stale": False}

    async def _fetch_with_retry(self) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(1, RETRY_COUNT + 1):
            try:
                return await self._fetch_once()
            except Exception as exc:
                last_exc = exc
                logger.warning("Gold live fetch attempt %d/%d failed: %s", attempt, RETRY_COUNT, exc)
                if attempt < RETRY_COUNT:
                    await asyncio.sleep(RETRY_BACKOFF * attempt)
        raise last_exc or RuntimeError("Gold live fetch failed")

    async def _fetch_once(self) -> dict[str, Any]:
        """یک تلاش برای جمع‌آوری قیمت‌ها از BrsApi."""
        # همه منابع را موازی بگیر
        commodities_task = self.brsapi.get_commodity_prices(category="precious_metal")
        currency_task = self.brsapi.get_commodity_prices(category="currency")
        commodities, currencies = await asyncio.gather(commodities_task, currency_task, return_exceptions=True)
        if isinstance(commodities, Exception):
            raise commodities
        if isinstance(currencies, Exception):
            raise currencies

        out: dict[str, float] = {
            "gold_oz_usd": 0.0,
            "gold_18k_irr": 0.0,
            "coin_bahar_irr": 0.0,
            "usd_irr": 0.0,
        }
        for item in commodities:
            sym = (item.get("symbol") or "").lower()
            price = item.get("price") or item.get("price_irr") or 0
            if "ounce" in sym or "oz" in sym:
                out["gold_oz_usd"] = float(price)
            elif "18" in sym or "18k" in sym:
                out["gold_18k_irr"] = float(price)
            elif "coin" in sym or "bahar" in sym or "sekke" in sym:
                out["coin_bahar_irr"] = float(price)
        for item in currencies:
            sym = (item.get("symbol") or "").lower()
            if "usd" in sym or "dollar" in sym:
                out["usd_irr"] = float(item.get("price") or 0)

        from core.time import utc_now_iso

        return {
            **out,
            "last_updated": utc_now_iso(),
            "source": "BrsApi.ir",
        }

    @staticmethod
    def _empty_shape(is_stale: bool, error: str | None = None) -> dict[str, Any]:
        from core.time import utc_now_iso

        return {
            "gold_oz_usd": 0.0,
            "gold_18k_irr": 0.0,
            "coin_bahar_irr": 0.0,
            "usd_irr": 0.0,
            "last_updated": utc_now_iso(),
            "source": "BrsApi.ir",
            "is_stale": is_stale,
            "error": error,
        }
