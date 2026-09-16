"""Crypto + Multi-Currency support.

افزودن BTC, ETH, EUR, GBP, AED به‌جز طلا/سکه/دلار.
از BrsApi symbols یا fallback CoinGecko (free public API).

هر asset:
- price (USD/IRT)
- bubble_pct (از 30-day MA)
- 24h change
- volatility (rolling std)
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from datetime import datetime

import httpx

from core.time import now_utc

logger = logging.getLogger(__name__)

REDIS_KEY_CRYPTO = "golddesk:crypto:cache"
CACHE_TTL = 300  # 5 min

# CoinGecko free API (no key needed)
COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
COINGECKO_HISTORY = "https://api.coingecko.com/api/v3/coins/{id}/market_chart"

# Map: our symbol → coingecko id
COINGECKO_IDS: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "USDT": "tether",
    "BNB": "binancecoin",
    "ADA": "cardano",
    "SOL": "solana",
    "XRP": "ripple",
    "DOGE": "dogecoin",
}

# FX (از open.er-api.com free)
FX_API = "https://open.er-api.com/v6/latest/USD"
FX_SYMBOLS: list[str] = ["EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "AED", "SAR", "TRY"]


@dataclass(frozen=True)
class AssetPrice:
    symbol: str
    name_fa: str
    price_usd: float
    price_irt: float
    change_24h_pct: float
    bubble_pct: float | None  # اگه history داشته باشیم
    source: str
    ts: datetime


# ── Crypto fetcher ─────────────────────────────────────────


async def fetch_crypto_prices(usd_irt_rate: float) -> list[AssetPrice]:
    """دریافت قیمت لحظه‌ای ارزهای دیجیتال از CoinGecko."""
    ids = ",".join(COINGECKO_IDS.values())
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                COINGECKO_URL,
                params={
                    "ids": ids,
                    "vs_currencies": "usd",
                    "include_24hr_change": "true",
                },
            )
            if r.status_code != 200:
                logger.warning("CoinGecko HTTP %s", r.status_code)
                return []
            data = r.json()

        out: list[AssetPrice] = []
        for sym, cg_id in COINGECKO_IDS.items():
            item = data.get(cg_id)
            if not item:
                continue
            usd = float(item.get("usd", 0))
            change = float(item.get("usd_24h_change", 0))
            out.append(
                AssetPrice(
                    symbol=sym,
                    name_fa=_name_fa(sym),
                    price_usd=usd,
                    price_irt=usd * usd_irt_rate,
                    change_24h_pct=change,
                    bubble_pct=None,
                    source="coingecko",
                    ts=now_utc(),
                )
            )
        return out
    except Exception as exc:
        logger.warning("crypto fetch failed: %s", exc)
        return []


# ── FX fetcher ────────────────────────────────────────────


async def fetch_fx_rates(base: str = "USD") -> dict[str, float]:
    """نرخ FX از open.er-api.com. Returns: symbol → IRT rate."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(FX_API, params={"base": base})
            if r.status_code != 200:
                return {}
            data = r.json()
            rates = data.get("rates", {})
            return {k: float(v) for k, v in rates.items() if k in FX_SYMBOLS}
    except Exception as exc:
        logger.warning("FX fetch failed: %s", exc)
        return {}


# ── Helpers ───────────────────────────────────────────────


def _name_fa(symbol: str) -> str:
    names = {
        "BTC": "بیت‌کوین",
        "ETH": "اتریوم",
        "USDT": "تتر",
        "BNB": "بایننس کوین",
        "ADA": "کاردانو",
        "SOL": "سولانا",
        "XRP": "ریپل",
        "DOGE": "دوج‌کوین",
        "EUR": "یورو",
        "GBP": "پوند",
        "JPY": "ین",
        "CHF": "فرانک",
        "CAD": "دلار کانادا",
        "AUD": "دلار استرالیا",
        "AED": "درهم",
        "SAR": "ریال عربستان",
        "TRY": "لیر",
    }
    return names.get(symbol, symbol)


def calc_bubble_from_history(prices: list[float]) -> float | None:
    """bubble = (current - MA30) / MA30 × 100. اگه history کمتر از 30، None."""
    if len(prices) < 30:
        return None
    arr = prices[-30:]
    ma = sum(arr) / 30
    if ma == 0:
        return None
    return (arr[-1] - ma) / ma * 100


# ── Cache layer ──────────────────────────────────────────


async def get_cached_or_fetch(fetcher, *args, cache_key: str, ttl: int = CACHE_TTL, **kwargs):
    """اجرای fetcher با cache در Redis."""
    with contextlib.suppress(Exception):
        from core.cache import get_cache

        cache = get_cache()
        raw = await cache.get(cache_key)
        if raw:
            import json

            return json.loads(raw) if isinstance(raw, str) else raw

    result = await fetcher(*args, **kwargs)
    if result:
        with contextlib.suppress(Exception):
            import json

            from core.cache import get_cache

            cache = get_cache()
            await cache.set(
                cache_key,
                json.dumps(result, default=str) if not isinstance(result, str) else result,
                ttl=ttl,
            )
    return result
